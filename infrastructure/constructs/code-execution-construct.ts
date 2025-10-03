import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface CodeExecutionConstructProps {
  maxExecutionTime?: number;
  maxMemoryMb?: number;
  maxOutputSize?: number;
}

export class CodeExecutionConstruct extends Construct {
  public readonly codeExecutionFunction: lambda.Function;
  public readonly executionRole: iam.Role;

  constructor(scope: Construct, id: string, props: CodeExecutionConstructProps = {}) {
    super(scope, id);

    // Default values
    const maxExecutionTime = props.maxExecutionTime || 30;
    const maxMemoryMb = props.maxMemoryMb || 512;
    const maxOutputSize = props.maxOutputSize || 10000;

    // Create IAM role for the code execution Lambda function
    this.executionRole = new iam.Role(this, 'CodeExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        CloudWatchLogs: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ],
              resources: [
                `arn:aws:logs:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:log-group:/aws/lambda/agent-scholar-code-execution*`
              ]
            })
          ]
        })
      }
    });

    // Create Lambda layer for scientific computing libraries
    const scientificLibrariesLayer = new lambda.LayerVersion(this, 'ScientificLibrariesLayer', {
      code: lambda.Code.fromAsset('layers/scientific-libraries'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Scientific computing libraries (NumPy, Pandas, Matplotlib, SciPy, etc.)'
    });

    // Create shared utilities layer
    const sharedUtilitiesLayer = new lambda.LayerVersion(this, 'SharedUtilitiesLayer', {
      code: lambda.Code.fromAsset('src/shared'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Shared utilities and models for Agent Scholar'
    });

    // Code Execution Lambda Function
    this.codeExecutionFunction = new lambda.Function(this, 'CodeExecutionFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'code_executor.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/code-execution'),
      layers: [scientificLibrariesLayer, sharedUtilitiesLayer],
      role: this.executionRole,
      timeout: cdk.Duration.minutes(Math.ceil(maxExecutionTime / 60) + 1), // Lambda timeout slightly higher than execution timeout
      memorySize: Math.max(maxMemoryMb, 512), // Minimum 512MB for scientific computing
      environment: {
        MAX_EXECUTION_TIME: maxExecutionTime.toString(),
        MAX_MEMORY_MB: maxMemoryMb.toString(),
        MAX_OUTPUT_SIZE: maxOutputSize.toString(),
        PYTHONPATH: '/opt/python:/var/runtime',
        AWS_REGION: cdk.Stack.of(this).region
      },
      description: 'Secure Python code execution for Agent Scholar - enables computational analysis and visualization',
      functionName: 'agent-scholar-code-execution'
    });

    // Create CloudWatch Log Group with retention
    new logs.LogGroup(this, 'CodeExecutionLogGroup', {
      logGroupName: `/aws/lambda/${this.codeExecutionFunction.functionName}`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // Output the function ARN and name
    new cdk.CfnOutput(this, 'CodeExecutionFunctionArn', {
      value: this.codeExecutionFunction.functionArn,
      description: 'ARN of the Code Execution Lambda function'
    });

    new cdk.CfnOutput(this, 'CodeExecutionFunctionName', {
      value: this.codeExecutionFunction.functionName,
      description: 'Name of the Code Execution Lambda function'
    });
  }

  /**
   * Grant permissions for Bedrock Agent to invoke this function
   */
  public grantInvokeToBedrockAgent(agentRole: iam.IRole): void {
    this.codeExecutionFunction.grantInvoke(agentRole);
  }

  /**
   * Create action group configuration for Bedrock Agent
   */
  public createActionGroupConfig(): any {
    return {
      actionGroupName: 'CodeExecutionActionGroup',
      description: 'Execute Python code for analysis, visualization, and validation of concepts',
      actionGroupExecutor: {
        lambda: this.codeExecutionFunction.functionArn
      },
      apiSchema: {
        payload: JSON.stringify({
          openapi: '3.0.0',
          info: {
            title: 'Code Execution API',
            version: '1.0.0',
            description: 'API for executing Python code in a secure sandboxed environment'
          },
          paths: {
            '/execute': {
              post: {
                summary: 'Execute Python code',
                description: 'Executes Python code in a secure, sandboxed environment with access to scientific computing libraries',
                operationId: 'executeCode',
                requestBody: {
                  required: true,
                  content: {
                    'application/json': {
                      schema: {
                        type: 'object',
                        properties: {
                          code: {
                            type: 'string',
                            description: 'Python code to execute',
                            minLength: 1,
                            maxLength: 10000
                          },
                          timeout: {
                            type: 'integer',
                            description: 'Maximum execution time in seconds',
                            minimum: 1,
                            maximum: 30,
                            default: 10
                          },
                          language: {
                            type: 'string',
                            description: 'Programming language (currently only Python supported)',
                            enum: ['python'],
                            default: 'python'
                          }
                        },
                        required: ['code']
                      }
                    }
                  }
                },
                responses: {
                  '200': {
                    description: 'Code execution results',
                    content: {
                      'application/json': {
                        schema: {
                          type: 'object',
                          properties: {
                            success: { type: 'boolean' },
                            output: { type: 'string' },
                            error: { type: 'string' },
                            execution_time: { type: 'number' },
                            visualizations: {
                              type: 'array',
                              items: {
                                type: 'object',
                                properties: {
                                  type: { type: 'string' },
                                  format: { type: 'string' },
                                  title: { type: 'string' },
                                  data: { type: 'string' },
                                  size: { type: 'number' }
                                }
                              }
                            },
                            variables: {
                              type: 'object',
                              additionalProperties: {
                                type: 'object',
                                properties: {
                                  type: { type: 'string' },
                                  value: { type: 'string' }
                                }
                              }
                            },
                            imports_used: {
                              type: 'array',
                              items: { type: 'string' }
                            }
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

  /**
   * Add custom security policies for code execution
   */
  public addSecurityPolicies(): void {
    // Add additional security policies if needed
    this.executionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.DENY,
        actions: [
          'ec2:*',
          's3:DeleteBucket',
          's3:DeleteObject',
          'iam:*',
          'lambda:*',
          'cloudformation:*'
        ],
        resources: ['*']
      })
    );
  }

  /**
   * Configure monitoring and alerting
   */
  public addMonitoring(): void {
    // Add CloudWatch alarms for monitoring
    const errorAlarm = new cdk.aws_cloudwatch.Alarm(this, 'CodeExecutionErrorAlarm', {
      metric: this.codeExecutionFunction.metricErrors(),
      threshold: 10,
      evaluationPeriods: 2,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING
    });

    const durationAlarm = new cdk.aws_cloudwatch.Alarm(this, 'CodeExecutionDurationAlarm', {
      metric: this.codeExecutionFunction.metricDuration(),
      threshold: 25000, // 25 seconds
      evaluationPeriods: 3,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING
    });

    // Output alarm ARNs
    new cdk.CfnOutput(this, 'ErrorAlarmArn', {
      value: errorAlarm.alarmArn,
      description: 'CloudWatch alarm for code execution errors'
    });

    new cdk.CfnOutput(this, 'DurationAlarmArn', {
      value: durationAlarm.alarmArn,
      description: 'CloudWatch alarm for code execution duration'
    });
  }
}