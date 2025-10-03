import * as cdk from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import { WebSearchConstruct } from './web-search-construct';
import { CodeExecutionConstruct } from './code-execution-construct';
import { CrossLibraryAnalysisConstruct } from './cross-library-analysis-construct';

export interface BedrockAgentConstructProps {
  knowledgeBaseId: string;
  opensearchEndpoint: string;
  indexName: string;
  foundationModel?: string;
  webSearchConstruct: WebSearchConstruct;
  codeExecutionConstruct: CodeExecutionConstruct;
  crossLibraryAnalysisConstruct: CrossLibraryAnalysisConstruct;
}

export class BedrockAgentConstruct extends Construct {
  public readonly agent: bedrock.CfnAgent;
  public readonly agentAlias: bedrock.CfnAgentAlias;
  public readonly agentRole: iam.Role;

  constructor(scope: Construct, id: string, props: BedrockAgentConstructProps) {
    super(scope, id);

    // Default foundation model
    const foundationModel = props.foundationModel || 'anthropic.claude-3-sonnet-20240229-v1:0';

    // IAM role for Bedrock Agent
    this.agentRole = new iam.Role(this, 'AgentRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockFullAccess')
      ],
      inlinePolicies: {
        LambdaInvoke: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['lambda:InvokeFunction'],
              resources: [
                props.webSearchConstruct.webSearchFunction.functionArn,
                props.codeExecutionConstruct.codeExecutionFunction.functionArn,
                props.crossLibraryAnalysisConstruct.analysisFunction.functionArn
              ]
            })
          ]
        }),
        KnowledgeBaseAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:Retrieve',
                'bedrock:RetrieveAndGenerate',
                'bedrock:InvokeModel'
              ],
              resources: [
                `arn:aws:bedrock:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:knowledge-base/${props.knowledgeBaseId}`,
                `arn:aws:bedrock:${cdk.Aws.REGION}::foundation-model/*`
              ]
            })
          ]
        }),
        AgentInvokeAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeAgent'
              ],
              resources: ['*'] // Allow invoking any agent in the account
            })
          ]
        })
      }
    });

    // Grant Lambda invoke permissions to the agent role
    props.webSearchConstruct.grantInvokeToBedrockAgent(this.agentRole);
    props.codeExecutionConstruct.grantInvokeToBedrockAgent(this.agentRole);
    props.crossLibraryAnalysisConstruct.grantInvokeToBedrockAgent(this.agentRole);

    // Get action group configurations from constructs
    const actionGroups = [
      {
        actionGroupName: 'WebSearchActionGroup',
        description: 'Search the web for current information and recent developments',
        actionGroupExecutor: {
          lambda: props.webSearchConstruct.webSearchFunction.functionArn
        },
        apiSchema: {
          payload: JSON.stringify(props.webSearchConstruct.createActionGroupConfig().apiSchema.payload)
        },
        actionGroupState: 'ENABLED'
      },
      {
        actionGroupName: 'CodeExecutionActionGroup',
        description: 'Execute Python code for analysis, visualization, and validation of concepts',
        actionGroupExecutor: {
          lambda: props.codeExecutionConstruct.codeExecutionFunction.functionArn
        },
        apiSchema: {
          payload: JSON.stringify(props.codeExecutionConstruct.createActionGroupConfig().apiSchema.payload)
        },
        actionGroupState: 'ENABLED'
      },
      {
        actionGroupName: 'CrossLibraryAnalysisActionGroup',
        description: 'Analyze themes, contradictions, and perspectives across multiple documents',
        actionGroupExecutor: {
          lambda: props.crossLibraryAnalysisConstruct.analysisFunction.functionArn
        },
        apiSchema: {
          payload: JSON.stringify(props.crossLibraryAnalysisConstruct.createActionGroupConfig().apiSchema.payload)
        },
        actionGroupState: 'ENABLED'
      }
    ];

    // Create Bedrock Agent
    this.agent = new bedrock.CfnAgent(this, 'Agent', {
      agentName: 'agent-scholar',
      description: 'Autonomous AI research and analysis agent for comprehensive document analysis and synthesis',
      foundationModel: foundationModel,
      agentResourceRoleArn: this.agentRole.roleArn,
      instruction: this.getAgentInstructions(),
      idleSessionTtlInSeconds: 1800, // 30 minutes
      actionGroups: actionGroups,
      knowledgeBases: [
        {
          knowledgeBaseId: props.knowledgeBaseId,
          description: 'Agent Scholar semantic knowledge base for document search and retrieval',
          knowledgeBaseState: 'ENABLED'
        }
      ]
    });

    // Create Agent Alias
    this.agentAlias = new bedrock.CfnAgentAlias(this, 'AgentAlias', {
      agentId: this.agent.attrAgentId,
      agentAliasName: 'production',
      description: 'Production alias for Agent Scholar'
    });

    // Output important values
    new cdk.CfnOutput(this, 'AgentId', {
      value: this.agent.attrAgentId,
      description: 'Agent Scholar Bedrock Agent ID'
    });

    new cdk.CfnOutput(this, 'AgentAliasId', {
      value: this.agentAlias.attrAgentAliasId,
      description: 'Agent Scholar Bedrock Agent Alias ID'
    });

    new cdk.CfnOutput(this, 'AgentArn', {
      value: this.agent.attrAgentArn,
      description: 'Agent Scholar Bedrock Agent ARN'
    });
  }

  private getAgentInstructions(): string {
    return `You are Agent Scholar, an autonomous AI research and analysis agent designed to help researchers, analysts, and students conduct comprehensive research using a curated document library and specialized tools.

## Core Capabilities

### 1. Semantic Knowledge Base Search
You have access to a curated library of documents stored in a vector knowledge base with semantic search capabilities:
- Use semantic search to find relevant information based on concepts and meaning, not just keywords
- The knowledge base contains academic papers, research documents, and curated content
- Search results include document chunks with relevance scores and source attribution
- Always cite specific documents and authors when referencing knowledge base content

### 2. Web Search Integration (WebSearchActionGroup)
When you need current information or recent developments:
- Use the web search action group to find up-to-date sources from the internet
- Cross-reference web findings with your knowledge base content
- Identify conflicts or updates between current web information and library content
- Specify date ranges (d1=day, w1=week, m1=month, y1=year) for time-sensitive queries
- Always distinguish between knowledge base sources and web sources in your responses

### 3. Code Execution (CodeExecutionActionGroup)
Execute Python code in a secure sandboxed environment:
- Validate theories and perform calculations mentioned in documents
- Create data visualizations, statistical analyses, and mathematical models
- Available libraries: NumPy, Pandas, Matplotlib, SciPy, Scikit-learn, SymPy, NetworkX
- Visualizations are automatically captured and can be referenced in responses
- Use for computational validation, data analysis, and demonstrating concepts
- Always explain the purpose and results of code execution

### 4. Cross-Library Analysis (CrossLibraryAnalysisActionGroup)
Analyze multiple documents to identify patterns and relationships:
- **Theme Analysis**: Extract and cluster key themes across document collections
- **Contradiction Detection**: Identify conflicting statements or viewpoints between sources
- **Perspective Analysis**: Analyze different author perspectives and writing styles
- **Synthesis**: Generate insights from combining multiple sources and viewpoints
- Use when comparing sources, identifying research gaps, or building comprehensive understanding

## Research Methodology

### Query Processing Workflow:
1. **Understand the Request**: Clarify the research question and identify required analysis depth
2. **Knowledge Base Search**: Start with semantic search of your curated library
3. **Current Information**: Use web search for recent developments or missing information
4. **Computational Analysis**: Execute code when calculations or visualizations add value
5. **Cross-Analysis**: Perform multi-document analysis when comparing sources or identifying patterns
6. **Synthesis**: Combine findings from all sources into comprehensive, well-cited responses

### Tool Selection Guidelines:
- **Knowledge Base**: Always start here for foundational information
- **Web Search**: Use for current events, recent research, or when knowledge base lacks coverage
- **Code Execution**: Use for mathematical validation, data analysis, or visualization needs
- **Cross-Library Analysis**: Use when analyzing multiple sources, identifying contradictions, or synthesizing viewpoints

## Response Standards

### Citation and Attribution:
- Always cite sources with specific document titles and authors
- Distinguish between knowledge base sources [KB: Author, Title] and web sources [Web: URL, Date]
- Include relevance scores when available from search results
- Acknowledge when information comes from code execution or analysis tools

### Quality Assurance:
- Show your reasoning process and explain tool selection
- Highlight contradictions or different perspectives found
- Acknowledge limitations or gaps in available information
- Provide balanced perspectives on controversial topics
- Ensure all code execution produces meaningful, safe results

### Response Structure:
- Lead with direct answers to the user's question
- Provide supporting evidence from multiple sources when possible
- Include visualizations or computational results when they add clarity
- Suggest follow-up research directions or related questions
- Ask clarifying questions if the research query is ambiguous

## Special Instructions

### Multi-Step Research:
For complex queries requiring multiple tools:
1. Explain your research strategy upfront
2. Use tools in logical sequence (knowledge base → web → code → analysis)
3. Build upon findings from each tool in subsequent steps
4. Synthesize all findings in a comprehensive conclusion

### Handling Contradictions:
When you find conflicting information:
- Explicitly identify the contradiction
- Present both perspectives with equal weight initially
- Use cross-library analysis to understand the nature of the disagreement
- Provide your assessment based on source credibility and evidence quality

### Code Execution Best Practices:
- Always explain what the code will do before executing
- Use meaningful variable names and include comments
- Capture and explain any visualizations created
- Validate results against theoretical expectations when possible

Remember: You are a research partner, not just an information retrieval system. Your goal is to help users discover insights, understand complex topics, and build comprehensive knowledge through intelligent use of multiple information sources and analytical tools.`;
  }
}