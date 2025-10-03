import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export interface WebSearchConstructProps {
  serpApiKey?: string;
  googleApiKey?: string;
  googleSearchEngineId?: string;
}

export class WebSearchConstruct extends Construct {
  public readonly webSearchFunction: lambda.Function;
  public readonly webSearchRole: iam.Role;

  constructor(scope: Construct, id: string, props: WebSearchConstructProps = {}) {
    super(scope, id);

    // Create IAM role for the web search Lambda function
    this.webSearchRole = new iam.Role(this, 'WebSearchRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        ParameterStoreAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters'
              ],
              resources: [
                `arn:aws:ssm:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:parameter/agent-scholar/web-search/*`
              ]
            })
          ]
        })
      }
    });

    // Store API keys in Parameter Store (if provided)
    if (props.serpApiKey) {
      new ssm.StringParameter(this, 'SerpApiKeyParameter', {
        parameterName: '/agent-scholar/web-search/serp-api-key',
        stringValue: props.serpApiKey,
        description: 'SERP API key for web search functionality',
        type: ssm.ParameterType.SECURE_STRING
      });
    }

    if (props.googleApiKey) {
      new ssm.StringParameter(this, 'GoogleApiKeyParameter', {
        parameterName: '/agent-scholar/web-search/google-api-key',
        stringValue: props.googleApiKey,
        description: 'Google Custom Search API key',
        type: ssm.ParameterType.SECURE_STRING
      });
    }

    if (props.googleSearchEngineId) {
      new ssm.StringParameter(this, 'GoogleSearchEngineIdParameter', {
        parameterName: '/agent-scholar/web-search/google-search-engine-id',
        stringValue: props.googleSearchEngineId,
        description: 'Google Custom Search Engine ID'
      });
    }

    // Create shared Lambda layer for dependencies
    const dependenciesLayer = new lambda.LayerVersion(this, 'WebSearchDependenciesLayer', {
      code: lambda.Code.fromAsset('layers/web-search-dependencies'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Dependencies for web search (requests, etc.)'
    });

    // Create shared utilities layer
    const sharedLayer = new lambda.LayerVersion(this, 'SharedUtilitiesLayer', {
      code: lambda.Code.fromAsset('src/shared'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Shared utilities and models for Agent Scholar'
    });

    // Web Search Lambda Function
    this.webSearchFunction = new lambda.Function(this, 'WebSearchFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'web_search.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/web-search'),
      layers: [dependenciesLayer, sharedLayer],
      role: this.webSearchRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        AWS_REGION: cdk.Stack.of(this).region,
        // API keys will be loaded from Parameter Store at runtime
        SERP_API_KEY_PARAM: '/agent-scholar/web-search/serp-api-key',
        GOOGLE_API_KEY_PARAM: '/agent-scholar/web-search/google-api-key',
        GOOGLE_SEARCH_ENGINE_ID_PARAM: '/agent-scholar/web-search/google-search-engine-id'
      },
      description: 'Web search action group for Agent Scholar - provides current information from the web'
    });

    // Output the function ARN and name
    new cdk.CfnOutput(this, 'WebSearchFunctionArn', {
      value: this.webSearchFunction.functionArn,
      description: 'ARN of the Web Search Lambda function'
    });

    new cdk.CfnOutput(this, 'WebSearchFunctionName', {
      value: this.webSearchFunction.functionName,
      description: 'Name of the Web Search Lambda function'
    });
  }

  /**
   * Grant permissions for Bedrock Agent to invoke this function
   */
  public grantInvokeToBedrockAgent(agentRole: iam.IRole): void {
    this.webSearchFunction.grantInvoke(agentRole);
  }

  /**
   * Create action group configuration for Bedrock Agent
   */
  public createActionGroupConfig(): any {
    return {
      actionGroupName: 'WebSearchActionGroup',
      description: 'Search the web for current information and recent developments',
      actionGroupExecutor: {
        lambda: this.webSearchFunction.functionArn
      },
      apiSchema: {
        payload: JSON.stringify({
          openapi: '3.0.0',
          info: {
            title: 'Web Search API',
            version: '1.0.0',
            description: 'API for searching current web information'
          },
          paths: {
            '/search': {
              post: {
                summary: 'Search the web for current information',
                description: 'Performs a web search to find current information and recent developments on a given topic',
                operationId: 'searchWeb',
                requestBody: {
                  required: true,
                  content: {
                    'application/json': {
                      schema: {
                        type: 'object',
                        properties: {
                          query: {
                            type: 'string',
                            description: 'The search query to find current information about',
                            minLength: 3,
                            maxLength: 200
                          },
                          max_results: {
                            type: 'integer',
                            description: 'Maximum number of search results to return',
                            minimum: 1,
                            maximum: 20,
                            default: 10
                          },
                          date_range: {
                            type: 'string',
                            description: 'Filter results by date range',
                            enum: ['d1', 'w1', 'm1', 'y1'],
                            default: 'y1'
                          },
                          location: {
                            type: 'string',
                            description: 'Geographic location for search context',
                            default: 'United States'
                          }
                        },
                        required: ['query']
                      }
                    }
                  }
                },
                responses: {
                  '200': {
                    description: 'Successful search results',
                    content: {
                      'application/json': {
                        schema: {
                          type: 'object',
                          properties: {
                            results: {
                              type: 'array',
                              items: {
                                type: 'object',
                                properties: {
                                  title: { type: 'string' },
                                  url: { type: 'string' },
                                  snippet: { type: 'string' },
                                  date: { type: 'string' },
                                  source: { type: 'string' },
                                  relevance_score: { type: 'number' }
                                }
                              }
                            },
                            total_results: { type: 'integer' },
                            search_query: { type: 'string' }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        })
      }
    };
  }
}