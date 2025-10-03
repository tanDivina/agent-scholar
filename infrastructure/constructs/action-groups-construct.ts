import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface ActionGroupsConstructProps {
  knowledgeBaseId: string;
  opensearchEndpoint: string;
}

export interface ActionGroupConfig {
  actionGroupName: string;
  description: string;
  lambdaFunction: lambda.Function;
  apiSchema: any;
}

export class ActionGroupsConstruct extends Construct {
  public readonly actionGroupConfigs: ActionGroupConfig[];

  constructor(scope: Construct, id: string, props: ActionGroupsConstructProps) {
    super(scope, id);

    // Common IAM role for Lambda functions
    const lambdaRole = new iam.Role(this, 'ActionGroupLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:RetrieveAndGenerate'
              ],
              resources: ['*']
            })
          ]
        })
      }
    });

    // Web Search Action Group Lambda
    const webSearchLambda = new lambda.Function(this, 'WebSearchLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'web_search.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/web-search'),
      functionName: 'agent-scholar-web-search',
      description: 'Web search action group for Agent Scholar',
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      role: lambdaRole,
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId
      }
    });

    // Code Execution Action Group Lambda
    const codeExecutionLambda = new lambda.Function(this, 'CodeExecutionLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'code_executor.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/code-execution'),
      functionName: 'agent-scholar-code-executor',
      description: 'Code execution action group for Agent Scholar',
      timeout: cdk.Duration.minutes(10),
      memorySize: 1024,
      role: lambdaRole,
      environment: {
        EXECUTION_TIMEOUT: '30'
      }
    });

    // Cross-Library Analysis Action Group Lambda
    const analysisLambda = new lambda.Function(this, 'AnalysisLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'analysis_engine.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/analysis'),
      functionName: 'agent-scholar-analysis-engine',
      description: 'Cross-library analysis action group for Agent Scholar',
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      role: lambdaRole,
      environment: {
        OPENSEARCH_ENDPOINT: props.opensearchEndpoint,
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId
      }
    });

    // Action Group configurations
    this.actionGroupConfigs = [
      {
        actionGroupName: 'WebSearchActionGroup',
        description: 'Search current information from the web to complement library knowledge',
        lambdaFunction: webSearchLambda,
        apiSchema: this.getWebSearchApiSchema()
      },
      {
        actionGroupName: 'CodeExecutionActionGroup',
        description: 'Execute Python code for analysis, visualization, and validation',
        lambdaFunction: codeExecutionLambda,
        apiSchema: this.getCodeExecutionApiSchema()
      },
      {
        actionGroupName: 'CrossLibraryAnalysisActionGroup',
        description: 'Analyze themes, contradictions, and perspectives across multiple documents',
        lambdaFunction: analysisLambda,
        apiSchema: this.getAnalysisApiSchema()
      }
    ];
  }

  private getWebSearchApiSchema(): any {
    return {
      openapi: '3.0.0',
      info: {
        title: 'Web Search API',
        version: '1.0.0',
        description: 'API for searching current information from the web'
      },
      paths: {
        '/search': {
          post: {
            description: 'Search for current information on the web',
            parameters: [
              {
                name: 'query',
                in: 'query',
                description: 'Search query string',
                required: true,
                schema: { type: 'string' }
              },
              {
                name: 'max_results',
                in: 'query',
                description: 'Maximum number of results to return',
                required: false,
                schema: { type: 'integer', default: 10 }
              },
              {
                name: 'date_range',
                in: 'query',
                description: 'Date range for search results (e.g., y1 for last year)',
                required: false,
                schema: { type: 'string', default: 'y1' }
              }
            ],
            responses: {
              '200': {
                description: 'Search results',
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
                              date: { type: 'string' }
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
        }
      }
    };
  }

  private getCodeExecutionApiSchema(): any {
    return {
      openapi: '3.0.0',
      info: {
        title: 'Code Execution API',
        version: '1.0.0',
        description: 'API for executing Python code in a sandboxed environment'
      },
      paths: {
        '/execute': {
          post: {
            description: 'Execute Python code and return results',
            parameters: [
              {
                name: 'code',
                in: 'query',
                description: 'Python code to execute',
                required: true,
                schema: { type: 'string' }
              },
              {
                name: 'timeout',
                in: 'query',
                description: 'Execution timeout in seconds',
                required: false,
                schema: { type: 'integer', default: 30 }
              }
            ],
            responses: {
              '200': {
                description: 'Code execution results',
                content: {
                  'application/json': {
                    schema: {
                      type: 'object',
                      properties: {
                        output: { type: 'string' },
                        error: { type: 'string' },
                        execution_time: { type: 'number' },
                        visualizations: {
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
    };
  }

  private getAnalysisApiSchema(): any {
    return {
      openapi: '3.0.0',
      info: {
        title: 'Cross-Library Analysis API',
        version: '1.0.0',
        description: 'API for analyzing themes, contradictions, and perspectives across documents'
      },
      paths: {
        '/analyze': {
          post: {
            description: 'Perform cross-library analysis on documents',
            parameters: [
              {
                name: 'analysis_type',
                in: 'query',
                description: 'Type of analysis to perform',
                required: true,
                schema: {
                  type: 'string',
                  enum: ['themes', 'contradictions', 'perspectives', 'synthesis']
                }
              },
              {
                name: 'document_ids',
                in: 'query',
                description: 'Comma-separated list of document IDs to analyze',
                required: false,
                schema: { type: 'string' }
              },
              {
                name: 'query_context',
                in: 'query',
                description: 'Context or topic for focused analysis',
                required: false,
                schema: { type: 'string' }
              }
            ],
            responses: {
              '200': {
                description: 'Analysis results',
                content: {
                  'application/json': {
                    schema: {
                      type: 'object',
                      properties: {
                        analysis_type: { type: 'string' },
                        results: {
                          type: 'array',
                          items: {
                            type: 'object',
                            properties: {
                              theme: { type: 'string' },
                              documents: { type: 'array', items: { type: 'string' } },
                              confidence: { type: 'number' },
                              details: { type: 'string' }
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
        }
      }
    };
  }
}