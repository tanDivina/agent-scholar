import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export interface ApiGatewayConstructProps {
  agentId: string;
  agentAliasId: string;
}

export class ApiGatewayConstruct extends Construct {
  public readonly apiEndpoint: string;
  public readonly sessionTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: ApiGatewayConstructProps) {
    super(scope, id);

    // DynamoDB table for session management
    this.sessionTable = new dynamodb.Table(this, 'SessionTable', {
      tableName: 'agent-scholar-sessions',
      partitionKey: {
        name: 'session_id',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      pointInTimeRecovery: true
    });

    // IAM role for the orchestrator Lambda
    const orchestratorRole = new iam.Role(this, 'OrchestratorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        BedrockAgentAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeAgent'
              ],
              resources: [
                `arn:aws:bedrock:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:agent/${props.agentId}`,
                `arn:aws:bedrock:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:agent-alias/${props.agentId}/${props.agentAliasId}`
              ]
            })
          ]
        }),
        DynamoDBAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
                'dynamodb:Scan'
              ],
              resources: [this.sessionTable.tableArn]
            })
          ]
        })
      }
    });

    // Lambda function for API orchestration
    const orchestratorLambda = new lambda.Function(this, 'OrchestratorLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'orchestrator.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/orchestrator'),
      functionName: 'agent-scholar-orchestrator',
      description: 'API orchestrator for Agent Scholar chat interface with session management',
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      role: orchestratorRole,
      environment: {
        AGENT_ID: props.agentId,
        AGENT_ALIAS_ID: props.agentAliasId,
        SESSION_TABLE_NAME: this.sessionTable.tableName
      }
    });

    // API Gateway REST API
    const api = new apigateway.RestApi(this, 'AgentScholarApi', {
      restApiName: 'agent-scholar-api',
      description: 'API Gateway for Agent Scholar chat interface',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token'
        ]
      },
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200
      }
    });

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(orchestratorLambda, {
      requestTemplates: {
        'application/json': JSON.stringify({
          body: '$input.json("$")',
          headers: {
            '#foreach($header in $input.params().header.keySet())': '"$header": "$util.escapeJavaScript($input.params().header.get($header))"#if($foreach.hasNext),#end',
            '#end': ''
          },
          queryStringParameters: {
            '#foreach($queryParam in $input.params().querystring.keySet())': '"$queryParam": "$util.escapeJavaScript($input.params().querystring.get($queryParam))"#if($foreach.hasNext),#end',
            '#end': ''
          }
        })
      },
      integrationResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': "'*'",
            'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
            'method.response.header.Access-Control-Allow-Methods': "'GET,POST,OPTIONS'"
          }
        }
      ]
    });

    // Chat endpoint
    const chatResource = api.root.addResource('chat');
    chatResource.addMethod('POST', lambdaIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
            'method.response.header.Access-Control-Allow-Headers': true,
            'method.response.header.Access-Control-Allow-Methods': true
          }
        }
      ]
    });

    // Session management endpoints
    const sessionResource = api.root.addResource('session');
    const sessionIdResource = sessionResource.addResource('{sessionId}');
    
    sessionIdResource.addMethod('GET', lambdaIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
            'method.response.header.Access-Control-Allow-Headers': true,
            'method.response.header.Access-Control-Allow-Methods': true
          }
        }
      ]
    });

    // Health check endpoint
    const healthResource = api.root.addResource('health');
    healthResource.addMethod('GET', lambdaIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
            'method.response.header.Access-Control-Allow-Headers': true,
            'method.response.header.Access-Control-Allow-Methods': true
          }
        }
      ]
    });

    this.apiEndpoint = api.url;
  }
}