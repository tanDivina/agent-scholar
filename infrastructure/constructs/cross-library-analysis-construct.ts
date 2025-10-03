import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface CrossLibraryAnalysisConstructProps {
  opensearchEndpoint: string;
  indexName: string;
}

export class CrossLibraryAnalysisConstruct extends Construct {
  public readonly analysisFunction: lambda.Function;
  public readonly analysisRole: iam.Role;

  constructor(scope: Construct, id: string, props: CrossLibraryAnalysisConstructProps) {
    super(scope, id);

    // Create IAM role for the cross-library analysis Lambda function
    this.analysisRole = new iam.Role(this, 'CrossLibraryAnalysisRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        OpenSearchAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'aoss:APIAccessAll'
              ],
              resources: ['*']
            })
          ]
        }),
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
                `arn:aws:logs:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:log-group:/aws/lambda/agent-scholar-cross-library-analysis*`
              ]
            })
          ]
        })
      }
    });

    // Create Lambda layer for analysis dependencies
    const analysisLibrariesLayer = new lambda.LayerVersion(this, 'AnalysisLibrariesLayer', {
      code: lambda.Code.fromAsset('layers/analysis-libraries'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Libraries for text analysis and NLP (NLTK, spaCy, etc.)'
    });

    // Create shared utilities layer
    const sharedUtilitiesLayer = new lambda.LayerVersion(this, 'SharedUtilitiesLayer', {
      code: lambda.Code.fromAsset('src/shared'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Shared utilities and models for Agent Scholar'
    });

    // Cross-Library Analysis Lambda Function
    this.analysisFunction = new lambda.Function(this, 'CrossLibraryAnalysisFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'analysis_engine.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/cross-library-analysis'),
      layers: [analysisLibrariesLayer, sharedUtilitiesLayer],
      role: this.analysisRole,
      timeout: cdk.Duration.minutes(10), // Analysis can take time
      memorySize: 1024, // Need memory for text processing
      environment: {
        OPENSEARCH_ENDPOINT: props.opensearchEndpoint,
        INDEX_NAME: props.indexName,
        AWS_REGION: cdk.Stack.of(this).region,
        PYTHONPATH: '/opt/python:/var/runtime'
      },
      description: 'Cross-library analysis for Agent Scholar - identifies themes, contradictions, and author perspectives',
      functionName: 'agent-scholar-cross-library-analysis'
    });

    // Create CloudWatch Log Group with retention
    new logs.LogGroup(this, 'CrossLibraryAnalysisLogGroup', {
      logGroupName: `/aws/lambda/${this.analysisFunction.functionName}`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // Output the function ARN and name
    new cdk.CfnOutput(this, 'CrossLibraryAnalysisFunctionArn', {
      value: this.analysisFunction.functionArn,
      description: 'ARN of the Cross-Library Analysis Lambda function'
    });

    new cdk.CfnOutput(this, 'CrossLibraryAnalysisFunctionName', {
      value: this.analysisFunction.functionName,
      description: 'Name of the Cross-Library Analysis Lambda function'
    });
  }

  /**
   * Grant permissions for Bedrock Agent to invoke this function
   */
  public grantInvokeToBedrockAgent(agentRole: iam.IRole): void {
    this.analysisFunction.grantInvoke(agentRole);
  }

  /**
   * Create action group configuration for Bedrock Agent
   */
  public createActionGroupConfig(): any {
    return {
      actionGroupName: 'CrossLibraryAnalysisActionGroup',
      description: 'Analyze themes, contradictions, and perspectives across multiple documents',
      actionGroupExecutor: {
        lambda: this.analysisFunction.functionArn
      },
      apiSchema: {
        payload: JSON.stringify({
          openapi: '3.0.0',
          info: {
            title: 'Cross-Library Analysis API',
            version: '1.0.0',
            description: 'API for analyzing themes, contradictions, and author perspectives across document collections'
          },
          paths: {
            '/analyze': {
              post: {
                summary: 'Perform cross-library analysis',
                description: 'Analyzes multiple documents to identify thematic connections, contradictions, and author perspectives',
                operationId: 'analyzeCrossLibrary',
                requestBody: {
                  required: true,
                  content: {
                    'application/json': {
                      schema: {
                        type: 'object',
                        properties: {
                          analysis_type: {
                            type: 'string',
                            description: 'Type of analysis to perform',
                            enum: ['comprehensive', 'themes', 'contradictions', 'perspectives'],
                            default: 'comprehensive'
                          },
                          query: {
                            type: 'string',
                            description: 'Optional query to filter documents for analysis',
                            maxLength: 500
                          },
                          document_ids: {
                            type: 'string',
                            description: 'Comma-separated list of specific document IDs to analyze',
                            maxLength: 1000
                          },
                          max_documents: {
                            type: 'integer',
                            description: 'Maximum number of documents to analyze',
                            minimum: 1,
                            maximum: 100,
                            default: 20
                          }
                        }
                      }
                    }
                  }
                },
                responses: {
                  '200': {
                    description: 'Analysis results',
                    content: {
                      'application/json': {
                        schema: {
                          type: 'object',
                          properties: {
                            analysis_timestamp: { type: 'string' },
                            documents_analyzed: { type: 'integer' },
                            theme_analysis: {
                              type: 'object',
                              properties: {
                                total_documents: { type: 'integer' },
                                top_themes: {
                                  type: 'array',
                                  items: {
                                    type: 'object',
                                    properties: {
                                      theme: { type: 'string' },
                                      frequency: { type: 'integer' },
                                      document_frequency: { type: 'integer' },
                                      relevance_score: { type: 'number' }
                                    }
                                  }
                                },
                                theme_clusters: {
                                  type: 'array',
                                  items: {
                                    type: 'object',
                                    properties: {
                                      cluster_name: { type: 'string' },
                                      themes: {
                                        type: 'array',
                                        items: { type: 'string' }
                                      },
                                      size: { type: 'integer' }
                                    }
                                  }
                                }
                              }
                            },
                            contradiction_analysis: {
                              type: 'object',
                              properties: {
                                total_documents_analyzed: { type: 'integer' },
                                contradictions_found: { type: 'integer' },
                                high_confidence_contradictions: {
                                  type: 'array',
                                  items: {
                                    type: 'object',
                                    properties: {
                                      document1: {
                                        type: 'object',
                                        properties: {
                                          id: { type: 'string' },
                                          title: { type: 'string' },
                                          statement: { type: 'string' }
                                        }
                                      },
                                      document2: {
                                        type: 'object',
                                        properties: {
                                          id: { type: 'string' },
                                          title: { type: 'string' },
                                          statement: { type: 'string' }
                                        }
                                      },
                                      confidence_score: { type: 'number' },
                                      contradiction_type: { type: 'string' }
                                    }
                                  }
                                }
                              }
                            },
                            perspective_analysis: {
                              type: 'object',
                              properties: {
                                total_authors: { type: 'integer' },
                                author_perspectives: {
                                  type: 'object',
                                  additionalProperties: {
                                    type: 'object',
                                    properties: {
                                      document_count: { type: 'integer' },
                                      total_content_length: { type: 'integer' },
                                      perspective_summary: {
                                        type: 'object',
                                        properties: {
                                          sentiment_tendency: { type: 'string' },
                                          certainty_tendency: { type: 'string' },
                                          perspective_traits: {
                                            type: 'array',
                                            items: { type: 'string' }
                                          }
                                        }
                                      }
                                    }
                                  }
                                },
                                diversity_analysis: {
                                  type: 'object',
                                  properties: {
                                    diversity_level: { type: 'string' },
                                    overall_diversity_score: { type: 'number' }
                                  }
                                }
                              }
                            },
                            synthesis: {
                              type: 'object',
                              properties: {
                                key_insights: {
                                  type: 'array',
                                  items: { type: 'string' }
                                },
                                recommendations: {
                                  type: 'array',
                                  items: { type: 'string' }
                                },
                                overall_assessment: {
                                  type: 'object',
                                  properties: {
                                    theme_coherence: { type: 'string' },
                                    consistency_level: { type: 'string' },
                                    perspective_diversity: { type: 'string' }
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
          }
        })
      }
    };
  }

  /**
   * Configure monitoring and alerting for analysis function
   */
  public addMonitoring(): void {
    // Add CloudWatch alarms for monitoring
    const errorAlarm = new cdk.aws_cloudwatch.Alarm(this, 'AnalysisErrorAlarm', {
      metric: this.analysisFunction.metricErrors(),
      threshold: 5,
      evaluationPeriods: 2,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING
    });

    const durationAlarm = new cdk.aws_cloudwatch.Alarm(this, 'AnalysisDurationAlarm', {
      metric: this.analysisFunction.metricDuration(),
      threshold: 300000, // 5 minutes
      evaluationPeriods: 2,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING
    });

    // Output alarm ARNs
    new cdk.CfnOutput(this, 'AnalysisErrorAlarmArn', {
      value: errorAlarm.alarmArn,
      description: 'CloudWatch alarm for cross-library analysis errors'
    });

    new cdk.CfnOutput(this, 'AnalysisDurationAlarmArn', {
      value: durationAlarm.alarmArn,
      description: 'CloudWatch alarm for cross-library analysis duration'
    });
  }
}