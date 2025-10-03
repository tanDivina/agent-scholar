import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { KnowledgeBaseConstruct } from './constructs/knowledge-base-construct';
import { OpenSearchConstruct } from './constructs/opensearch-construct';
import { DocumentIndexingConstruct } from './constructs/document-indexing-construct';
import { WebSearchConstruct } from './constructs/web-search-construct';
import { CodeExecutionConstruct } from './constructs/code-execution-construct';
import { CrossLibraryAnalysisConstruct } from './constructs/cross-library-analysis-construct';
import { BedrockAgentConstruct } from './constructs/bedrock-agent-construct';
import { ApiGatewayConstruct } from './constructs/api-gateway-construct';
import { MonitoringConstruct } from './constructs/monitoring-construct';
import { SecurityConstruct } from './constructs/security-construct';
import { CognitoConstruct } from './constructs/cognito-construct';

export interface AgentScholarStackProps extends cdk.StackProps {
  // Optional configuration parameters
  foundationModel?: string;
  collectionName?: string;
  indexName?: string;
  embeddingModelArn?: string;
  
  // API keys for external services (optional)
  serpApiKey?: string;
  googleApiKey?: string;
  googleSearchEngineId?: string;
  
  // Monitoring configuration
  alertEmail?: string;
}

export class AgentScholarStack extends cdk.Stack {
  public readonly knowledgeBase: KnowledgeBaseConstruct;
  public readonly openSearch: OpenSearchConstruct;
  public readonly documentIndexing: DocumentIndexingConstruct;
  public readonly webSearch: WebSearchConstruct;
  public readonly codeExecution: CodeExecutionConstruct;
  public readonly crossLibraryAnalysis: CrossLibraryAnalysisConstruct;
  public readonly bedrockAgent: BedrockAgentConstruct;
  public readonly apiGateway: ApiGatewayConstruct;
  public readonly monitoring: MonitoringConstruct;
  public readonly security: SecurityConstruct;
  public readonly cognito: CognitoConstruct;

  constructor(scope: Construct, id: string, props: AgentScholarStackProps = {}) {
    super(scope, id, props);

    // Configuration with defaults
    const config = {
      foundationModel: props.foundationModel || 'anthropic.claude-3-sonnet-20240229-v1:0',
      collectionName: props.collectionName || 'agent-scholar-collection',
      indexName: props.indexName || 'agent-scholar-documents',
      embeddingModelArn: props.embeddingModelArn || 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1'
    };

    // 1. Create OpenSearch Serverless infrastructure
    this.openSearch = new OpenSearchConstruct(this, 'OpenSearch', {
      collectionName: config.collectionName,
      indexName: config.indexName
    });

    // 2. Create Knowledge Base with S3 and OpenSearch integration
    this.knowledgeBase = new KnowledgeBaseConstruct(this, 'KnowledgeBase', {
      collectionName: config.collectionName,
      indexName: config.indexName,
      embeddingModelArn: config.embeddingModelArn
    });

    // 3. Create Document Indexing infrastructure
    this.documentIndexing = new DocumentIndexingConstruct(this, 'DocumentIndexing', {
      opensearchEndpoint: this.openSearch.collectionEndpoint,
      indexName: config.indexName,
      documentsS3Bucket: this.knowledgeBase.documentsBucket,
      opensearchAccessPolicy: [this.openSearch.createAccessPolicy([]).principal]
    });

    // 4. Create Web Search Action Group
    this.webSearch = new WebSearchConstruct(this, 'WebSearch', {
      serpApiKey: props.serpApiKey,
      googleApiKey: props.googleApiKey,
      googleSearchEngineId: props.googleSearchEngineId
    });

    // 5. Create Code Execution Action Group
    this.codeExecution = new CodeExecutionConstruct(this, 'CodeExecution', {
      maxExecutionTime: 30,
      maxMemoryMb: 512,
      maxOutputSize: 10000
    });

    // 6. Create Cross-Library Analysis Action Group
    this.crossLibraryAnalysis = new CrossLibraryAnalysisConstruct(this, 'CrossLibraryAnalysis', {
      opensearchEndpoint: this.openSearch.collectionEndpoint,
      indexName: config.indexName
    });

    // 7. Create Bedrock Agent with all action groups
    this.bedrockAgent = new BedrockAgentConstruct(this, 'BedrockAgent', {
      knowledgeBaseId: this.knowledgeBase.knowledgeBaseId,
      opensearchEndpoint: this.openSearch.collectionEndpoint,
      indexName: config.indexName,
      foundationModel: config.foundationModel,
      webSearchConstruct: this.webSearch,
      codeExecutionConstruct: this.codeExecution,
      crossLibraryAnalysisConstruct: this.crossLibraryAnalysis
    });

    // 8. Create security infrastructure
    this.security = new SecurityConstruct(this, 'Security', {
      enableWaf: true
    });

    // 9. Create Cognito authentication
    this.cognito = new CognitoConstruct(this, 'Cognito', {
      domainPrefix: 'agent-scholar-auth',
      enableMfa: false, // Set to true for production
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
        tempPasswordValidity: cdk.Duration.days(7)
      }
    });

    // 10. Create API Gateway and orchestrator with security integration
    this.apiGateway = new ApiGatewayConstruct(this, 'ApiGateway', {
      agentId: this.bedrockAgent.agent.attrAgentId,
      agentAliasId: this.bedrockAgent.agentAlias.attrAgentAliasId,
      cognitoUserPool: this.cognito.userPool,
      securityRole: this.security.securityRole
    });

    // Update security construct with API Gateway ARN for WAF
    this.security = new SecurityConstruct(this, 'SecurityWithWAF', {
      enableWaf: true,
      apiGatewayArn: this.apiGateway.api.deploymentStage.stageArn
    });

    // 11. Create comprehensive monitoring and alerting
    this.monitoring = new MonitoringConstruct(this, 'Monitoring', {
      lambdaFunctions: [
        this.documentIndexing.documentIndexingFunction,
        this.webSearch.webSearchFunction,
        this.codeExecution.codeExecutionFunction,
        this.crossLibraryAnalysis.analysisFunction,
        // Add orchestrator function from API Gateway construct
      ],
      apiGateway: this.apiGateway.apiEndpoint as any,
      alertEmail: props.alertEmail
    });

    // Stack-level outputs
    new cdk.CfnOutput(this, 'StackSummary', {
      value: JSON.stringify({
        agentId: this.bedrockAgent.agent.attrAgentId,
        agentAliasId: this.bedrockAgent.agentAlias.attrAgentAliasId,
        knowledgeBaseId: this.knowledgeBase.knowledgeBaseId,
        opensearchEndpoint: this.openSearch.collectionEndpoint,
        documentsBucket: this.knowledgeBase.documentsBucket.bucketName
      }),
      description: 'Agent Scholar deployment summary'
    });

    new cdk.CfnOutput(this, 'DeploymentInstructions', {
      value: `
Agent Scholar has been deployed successfully!

Next steps:
1. Upload documents to S3 bucket: ${this.knowledgeBase.documentsBucket.bucketName}/documents/
2. Configure API keys for web search (optional):
   - SERP API: Update parameter /agent-scholar/web-search/serp-api-key
   - Google Custom Search: Update parameters for API key and search engine ID
3. Test the agent using the Bedrock console or API
4. Use Agent ID: ${this.bedrockAgent.agent.attrAgentId}
5. Use Agent Alias ID: ${this.bedrockAgent.agentAlias.attrAgentAliasId}

For testing, you can invoke the agent with queries like:
- "Analyze the themes in my document library"
- "Search for recent developments in machine learning and compare with my documents"
- "Execute code to visualize the data trends mentioned in the research papers"
- "Find contradictions between different authors' perspectives on AI ethics"
      `,
      description: 'Instructions for using Agent Scholar after deployment'
    });

    // Add tags to all resources
    cdk.Tags.of(this).add('Project', 'AgentScholar');
    cdk.Tags.of(this).add('Environment', 'Production');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }

  /**
   * Add monitoring and alerting to all components
   */
  public addMonitoring(): void {
    // Add monitoring to individual components
    this.codeExecution.addMonitoring();
    this.crossLibraryAnalysis.addMonitoring();
    
    // Stack-level monitoring could be added here
    // For example, a dashboard combining metrics from all components
  }

  /**
   * Configure additional security policies
   */
  public addSecurityPolicies(): void {
    // Add additional security policies to components
    this.codeExecution.addSecurityPolicies();
    
    // Stack-level security policies could be added here
  }

  /**
   * Get deployment configuration for external tools
   */
  public getDeploymentConfig(): any {
    return {
      agentId: this.bedrockAgent.agent.attrAgentId,
      agentAliasId: this.bedrockAgent.agentAlias.attrAgentAliasId,
      knowledgeBaseId: this.knowledgeBase.knowledgeBaseId,
      opensearchEndpoint: this.openSearch.collectionEndpoint,
      documentsBucket: this.knowledgeBase.documentsBucket.bucketName,
      indexName: this.openSearch.indexName,
      actionGroups: {
        webSearch: this.webSearch.webSearchFunction.functionName,
        codeExecution: this.codeExecution.codeExecutionFunction.functionName,
        crossLibraryAnalysis: this.crossLibraryAnalysis.analysisFunction.functionName
      }
    };
  }
}