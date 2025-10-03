import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import { Construct } from 'constructs';

export interface DocumentIndexingConstructProps {
  opensearchEndpoint: string;
  indexName: string;
  documentsBucket: s3.Bucket;
}

export class DocumentIndexingConstruct extends Construct {
  public readonly indexingFunction: lambda.Function;
  public readonly processingQueue: sqs.Queue;

  constructor(scope: Construct, id: string, props: DocumentIndexingConstructProps) {
    super(scope, id);

    // Dead letter queue for failed processing
    const deadLetterQueue = new sqs.Queue(this, 'DocumentProcessingDLQ', {
      queueName: 'agent-scholar-document-processing-dlq',
      retentionPeriod: cdk.Duration.days(14)
    });

    // Main processing queue
    this.processingQueue = new sqs.Queue(this, 'DocumentProcessingQueue', {
      queueName: 'agent-scholar-document-processing',
      visibilityTimeout: cdk.Duration.minutes(15),
      deadLetterQueue: {
        queue: deadLetterQueue,
        maxReceiveCount: 3
      }
    });

    // IAM role for the indexing Lambda function
    const indexingRole = new iam.Role(this, 'DocumentIndexingRole', {
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
                'bedrock:RetrieveAndGenerate',
                'bedrock:StartIngestionJob',
                'bedrock:GetIngestionJob',
                'bedrock:ListIngestionJobs'
              ],
              resources: ['*']
            })
          ]
        }),
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:PutObject',
                's3:DeleteObject',
                's3:ListBucket'
              ],
              resources: [
                props.documentsBucket.bucketArn,
                `${props.documentsBucket.bucketArn}/*`
              ]
            })
          ]
        }),
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
        SQSAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:ReceiveMessage',
                'sqs:DeleteMessage',
                'sqs:GetQueueAttributes'
              ],
              resources: [this.processingQueue.queueArn]
            })
          ]
        })
      }
    });

    // Document indexing Lambda function
    this.indexingFunction = new lambda.Function(this, 'DocumentIndexingFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'document_indexer.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/document-indexing'),
      functionName: 'agent-scholar-document-indexer',
      description: 'Processes and indexes documents for Agent Scholar knowledge base',
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      role: indexingRole,
      environment: {
        OPENSEARCH_ENDPOINT: props.opensearchEndpoint,
        INDEX_NAME: props.indexName,
        DOCUMENTS_BUCKET: props.documentsBucket.bucketName,
        PROCESSING_QUEUE_URL: this.processingQueue.queueUrl,
        AWS_REGION: cdk.Stack.of(this).region
      }
    });

    // Add SQS event source to the Lambda function
    this.indexingFunction.addEventSource(
      new lambdaEventSources.SqsEventSource(this.processingQueue, {
        batchSize: 5,
        maxBatchingWindow: cdk.Duration.seconds(30)
      })
    );

    // S3 bucket notification to trigger processing
    props.documentsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.SqsDestination(this.processingQueue),
      { prefix: 'documents/' }
    );

    // Batch processing Lambda function for bulk operations
    const batchProcessingFunction = new lambda.Function(this, 'BatchProcessingFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'batch_processor.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/document-indexing'),
      functionName: 'agent-scholar-batch-processor',
      description: 'Batch processing for multiple documents',
      timeout: cdk.Duration.minutes(15),
      memorySize: 3008,
      role: indexingRole,
      environment: {
        OPENSEARCH_ENDPOINT: props.opensearchEndpoint,
        INDEX_NAME: props.indexName,
        DOCUMENTS_BUCKET: props.documentsBucket.bucketName,
        INDEXING_FUNCTION_NAME: this.indexingFunction.functionName,
        AWS_REGION: cdk.Stack.of(this).region
      }
    });

    // Grant the batch processor permission to invoke the indexing function
    this.indexingFunction.grantInvoke(batchProcessingFunction);

    // Output the function ARNs
    new cdk.CfnOutput(this, 'DocumentIndexingFunctionArn', {
      value: this.indexingFunction.functionArn,
      description: 'ARN of the document indexing Lambda function'
    });

    new cdk.CfnOutput(this, 'BatchProcessingFunctionArn', {
      value: batchProcessingFunction.functionArn,
      description: 'ARN of the batch processing Lambda function'
    });

    new cdk.CfnOutput(this, 'ProcessingQueueUrl', {
      value: this.processingQueue.queueUrl,
      description: 'URL of the document processing SQS queue'
    });
  }
}