import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { KnowledgeBaseConstruct } from '../constructs/knowledge-base-construct';
import { ActionGroupsConstruct } from '../constructs/action-groups-construct';
import { BedrockAgentConstruct } from '../constructs/bedrock-agent-construct';
import { ApiGatewayConstruct } from '../constructs/api-gateway-construct';

export class AgentScholarStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Knowledge Base with OpenSearch Serverless and Titan embeddings
    const knowledgeBase = new KnowledgeBaseConstruct(this, 'KnowledgeBase', {
      collectionName: 'agent-scholar-kb',
      indexName: 'documents',
      embeddingModelArn: this.getEmbeddingModelArn()
    });

    // Action Groups (Lambda functions for specialized capabilities)
    const actionGroups = new ActionGroupsConstruct(this, 'ActionGroups', {
      knowledgeBaseId: knowledgeBase.knowledgeBaseId,
      opensearchEndpoint: knowledgeBase.opensearchEndpoint
    });

    // Bedrock Agent configuration
    const bedrockAgent = new BedrockAgentConstruct(this, 'BedrockAgent', {
      knowledgeBaseId: knowledgeBase.knowledgeBaseId,
      actionGroups: actionGroups.actionGroupConfigs,
      foundationModel: 'anthropic.claude-3-sonnet-20240229-v1:0'
    });

    // API Gateway for external access
    const apiGateway = new ApiGatewayConstruct(this, 'ApiGateway', {
      agentId: bedrockAgent.agentId,
      agentAliasId: bedrockAgent.agentAliasId
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'AgentId', {
      value: bedrockAgent.agentId,
      description: 'Bedrock Agent ID'
    });

    new cdk.CfnOutput(this, 'AgentAliasId', {
      value: bedrockAgent.agentAliasId,
      description: 'Bedrock Agent Alias ID'
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: apiGateway.apiEndpoint,
      description: 'API Gateway endpoint for chat interface'
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: knowledgeBase.knowledgeBaseId,
      description: 'Knowledge Base ID for document ingestion'
    });

    new cdk.CfnOutput(this, 'OpenSearchEndpoint', {
      value: knowledgeBase.opensearchEndpoint,
      description: 'OpenSearch Serverless collection endpoint'
    });

    new cdk.CfnOutput(this, 'DocumentsBucketName', {
      value: knowledgeBase.documentsBucket.bucketName,
      description: 'S3 bucket for document storage'
    });
  }

  private getEmbeddingModelArn(): string {
    return `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v1`;
  }
}