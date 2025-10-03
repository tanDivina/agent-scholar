import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface OptimizedLambdaProps {
  functionName: string;
  codePath: string;
  handler: string;
  runtime?: lambda.Runtime;
  memorySize?: number;
  timeout?: cdk.Duration;
  environment?: { [key: string]: string };
  layers?: lambda.ILayerVersion[];
  vpc?: ec2.IVpc;
  securityGroups?: ec2.ISecurityGroup[];
  reservedConcurrency?: number;
  provisionedConcurrency?: number;
  deadLetterQueue?: boolean;
  enableXRay?: boolean;
  enableInsights?: boolean;
  logRetention?: logs.RetentionDays;
  performanceOptimizations?: {
    enableSnapStart?: boolean;
    enableCodeGuru?: boolean;
    enablePerformanceInsights?: boolean;
    warmupSchedule?: string;
  };
}

export class OptimizedLambdaConstruct extends Construct {
  public readonly function: lambda.Function;
  public readonly logGroup: logs.LogGroup;
  public readonly alias: lambda.Alias;
  public readonly version: lambda.Version;

  constructor(scope: Construct, id: string, props: OptimizedLambdaProps) {
    super(scope, id);

    // Create optimized log group
    this.logGroup = new logs.LogGroup(this, 'LogGroup', {
      logGroupName: `/aws/lambda/${props.functionName}`,
      retention: props.logRetention || logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // Determine optimal memory size based on function type
    const memorySize = this.calculateOptimalMemorySize(props);

    // Create performance-optimized Lambda function
    this.function = new lambda.Function(this, 'Function', {
      functionName: props.functionName,
      runtime: props.runtime || lambda.Runtime.PYTHON_3_11,
      handler: props.handler,
      code: lambda.Code.fromAsset(props.codePath),
      memorySize: memorySize,
      timeout: props.timeout || cdk.Duration.seconds(30),
      environment: {
        ...props.environment,
        // Performance optimization environment variables
        PYTHONPATH: '/opt/python:/var/runtime',
        AWS_LAMBDA_EXEC_WRAPPER: '/opt/bootstrap',
        _LAMBDA_TELEMETRY_LOG_LEVEL: 'ERROR',
        // Connection pooling settings
        AWS_LAMBDA_DOTNET_PREJIT: 'ProvisionedConcurrency',
        // Memory optimization
        NODE_OPTIONS: '--max-old-space-size=3008',
        // Enable performance features
        ENABLE_PERFORMANCE_MONITORING: 'true',
        ENABLE_CACHING: 'true',
        CACHE_TTL: '3600'
      },
      layers: [
        ...props.layers || [],
        this.createPerformanceLayer()
      ],
      vpc: props.vpc,
      securityGroups: props.securityGroups,
      reservedConcurrency: props.reservedConcurrency,
      logGroup: this.logGroup,
      tracing: props.enableXRay ? lambda.Tracing.ACTIVE : lambda.Tracing.DISABLED,
      insightsVersion: props.enableInsights ? lambda.LambdaInsightsVersion.VERSION_1_0_229_0 : undefined,
      deadLetterQueue: props.deadLetterQueue ? new cdk.aws_sqs.Queue(this, 'DLQ', {
        queueName: `${props.functionName}-dlq`,
        retentionPeriod: cdk.Duration.days(14)
      }) : undefined,
      // Performance optimizations
      architecture: lambda.Architecture.ARM_64, // Better price-performance
      bundling: {
        minify: true,
        sourceMap: false,
        target: 'es2020'
      }
    });

    // Apply SnapStart for Java functions (if applicable)
    if (props.performanceOptimizations?.enableSnapStart && 
        props.runtime?.family === lambda.RuntimeFamily.JAVA) {
      const cfnFunction = this.function.node.defaultChild as lambda.CfnFunction;
      cfnFunction.snapStart = { applyOn: 'PublishedVersions' };
    }

    // Create optimized version and alias
    this.version = this.function.currentVersion;
    this.alias = new lambda.Alias(this, 'Alias', {
      aliasName: 'live',
      version: this.version,
      provisionedConcurrencyConfig: props.provisionedConcurrency ? {
        provisionedConcurrentExecutions: props.provisionedConcurrency
      } : undefined
    });

    // Add performance monitoring permissions
    this.function.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'cloudwatch:PutMetricData',
        'xray:PutTraceSegments',
        'xray:PutTelemetryRecords'
      ],
      resources: ['*']
    }));

    // Configure CodeGuru Profiler if enabled
    if (props.performanceOptimizations?.enableCodeGuru) {
      this.enableCodeGuruProfiler();
    }

    // Set up warmup schedule if specified
    if (props.performanceOptimizations?.warmupSchedule) {
      this.createWarmupSchedule(props.performanceOptimizations.warmupSchedule);
    }

    // Add custom performance metrics
    this.addCustomMetrics();

    // Output function information
    new cdk.CfnOutput(this, 'FunctionArn', {
      value: this.function.functionArn,
      description: `ARN of optimized Lambda function ${props.functionName}`
    });

    new cdk.CfnOutput(this, 'FunctionName', {
      value: this.function.functionName,
      description: `Name of optimized Lambda function`
    });
  }

  private calculateOptimalMemorySize(props: OptimizedLambdaProps): number {
    // Return specified memory size if provided
    if (props.memorySize) {
      return props.memorySize;
    }

    // Calculate optimal memory based on function characteristics
    const functionType = this.determineFunctionType(props.functionName);
    
    switch (functionType) {
      case 'orchestrator':
        return 1024; // High memory for coordination logic
      case 'document-processing':
        return 2048; // High memory for document parsing and embedding
      case 'web-search':
        return 512;  // Medium memory for API calls
      case 'code-execution':
        return 1536; // High memory for code execution
      case 'analysis':
        return 1024; // Medium-high memory for analysis
      case 'auth':
        return 256;  // Low memory for authentication
      default:
        return 512;  // Default medium memory
    }
  }

  private determineFunctionType(functionName: string): string {
    const name = functionName.toLowerCase();
    
    if (name.includes('orchestrator')) return 'orchestrator';
    if (name.includes('document') || name.includes('indexing')) return 'document-processing';
    if (name.includes('search') || name.includes('web')) return 'web-search';
    if (name.includes('code') || name.includes('execution')) return 'code-execution';
    if (name.includes('analysis') || name.includes('cross-library')) return 'analysis';
    if (name.includes('auth')) return 'auth';
    
    return 'general';
  }

  private createPerformanceLayer(): lambda.LayerVersion {
    return new lambda.LayerVersion(this, 'PerformanceLayer', {
      layerVersionName: 'agent-scholar-performance-layer',
      code: lambda.Code.fromAsset('layers/performance', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'pip install --no-cache-dir -r requirements.txt -t /asset-output/python && ' +
            'cp -r src/* /asset-output/python/'
          ]
        }
      }),
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_11,
        lambda.Runtime.PYTHON_3_10,
        lambda.Runtime.PYTHON_3_9
      ],
      description: 'Performance optimization utilities and dependencies'
    });
  }

  private enableCodeGuruProfiler(): void {
    // Add CodeGuru Profiler permissions
    this.function.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'codeguru-profiler:ConfigureAgent',
        'codeguru-profiler:CreateProfilingGroup',
        'codeguru-profiler:PostAgentProfile'
      ],
      resources: ['*']
    }));

    // Add CodeGuru environment variables
    this.function.addEnvironment('AWS_CODEGURU_PROFILER_GROUP_NAME', this.function.functionName);
    this.function.addEnvironment('AWS_CODEGURU_PROFILER_ENABLED', 'true');
  }

  private createWarmupSchedule(scheduleExpression: string): void {
    // Create EventBridge rule for warmup
    const warmupRule = new cdk.aws_events.Rule(this, 'WarmupRule', {
      schedule: cdk.aws_events.Schedule.expression(scheduleExpression),
      description: `Warmup schedule for ${this.function.functionName}`
    });

    // Add Lambda target
    warmupRule.addTarget(new cdk.aws_events_targets.LambdaFunction(this.function, {
      event: cdk.aws_events.RuleTargetInput.fromObject({
        warmup: true,
        timestamp: cdk.aws_events.EventField.fromPath('$.time')
      })
    }));

    // Grant EventBridge permission to invoke function
    this.function.addPermission('AllowEventBridge', {
      principal: new iam.ServicePrincipal('events.amazonaws.com'),
      sourceArn: warmupRule.ruleArn
    });
  }

  private addCustomMetrics(): void {
    // Create custom metric filter for performance monitoring
    new logs.MetricFilter(this, 'PerformanceMetricFilter', {
      logGroup: this.logGroup,
      metricNamespace: 'AgentScholar/Performance',
      metricName: 'ExecutionTime',
      filterPattern: logs.FilterPattern.literal('[timestamp, requestId, level="PERFORMANCE", executionTime]'),
      metricValue: '$executionTime',
      defaultValue: 0
    });

    // Memory utilization metric
    new logs.MetricFilter(this, 'MemoryMetricFilter', {
      logGroup: this.logGroup,
      metricNamespace: 'AgentScholar/Performance',
      metricName: 'MemoryUtilization',
      filterPattern: logs.FilterPattern.literal('[timestamp, requestId, level="MEMORY", memoryUsed, memoryTotal]'),
      metricValue: '($memoryUsed/$memoryTotal)*100',
      defaultValue: 0
    });

    // Cache hit rate metric
    new logs.MetricFilter(this, 'CacheHitRateFilter', {
      logGroup: this.logGroup,
      metricNamespace: 'AgentScholar/Performance',
      metricName: 'CacheHitRate',
      filterPattern: logs.FilterPattern.literal('[timestamp, requestId, level="CACHE", hitRate]'),
      metricValue: '$hitRate',
      defaultValue: 0
    });

    // Error rate metric
    new logs.MetricFilter(this, 'ErrorRateFilter', {
      logGroup: this.logGroup,
      metricNamespace: 'AgentScholar/Performance',
      metricName: 'ErrorRate',
      filterPattern: logs.FilterPattern.literal('[timestamp, requestId, level="ERROR"]'),
      metricValue: '1',
      defaultValue: 0
    });
  }

  public addPerformanceAlarm(
    metricName: string,
    threshold: number,
    comparisonOperator: cdk.aws_cloudwatch.ComparisonOperator,
    alarmTopic: cdk.aws_sns.Topic
  ): cdk.aws_cloudwatch.Alarm {
    const alarm = new cdk.aws_cloudwatch.Alarm(this, `${metricName}Alarm`, {
      metric: new cdk.aws_cloudwatch.Metric({
        namespace: 'AgentScholar/Performance',
        metricName: metricName,
        dimensionsMap: {
          FunctionName: this.function.functionName
        },
        statistic: 'Average'
      }),
      threshold: threshold,
      comparisonOperator: comparisonOperator,
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: `${metricName} alarm for ${this.function.functionName}`
    });

    alarm.addAlarmAction(new cdk.aws_cloudwatch_actions.SnsAction(alarmTopic));
    return alarm;
  }

  public enablePerformanceInsights(): void {
    // Add performance insights configuration
    this.function.addEnvironment('ENABLE_PERFORMANCE_INSIGHTS', 'true');
    this.function.addEnvironment('PERFORMANCE_SAMPLE_RATE', '0.1'); // 10% sampling

    // Add X-Ray subsegments for detailed tracing
    this.function.addEnvironment('_X_AMZN_TRACE_ID', 'Root=1-5e1b4151-5ac6c58dc39e1ef1126bb7bb');
  }

  public configureConnectionPooling(maxConnections: number = 50): void {
    // Configure connection pooling environment variables
    this.function.addEnvironment('MAX_POOL_CONNECTIONS', maxConnections.toString());
    this.function.addEnvironment('CONNECTION_TIMEOUT', '5');
    this.function.addEnvironment('READ_TIMEOUT', '30');
    this.function.addEnvironment('RETRY_MODE', 'adaptive');
    this.function.addEnvironment('MAX_RETRY_ATTEMPTS', '3');
  }

  public enableCaching(cacheConfig: {
    enableRedis?: boolean;
    redisUrl?: string;
    memoryCache?: boolean;
    defaultTtl?: number;
  }): void {
    // Configure caching environment variables
    this.function.addEnvironment('ENABLE_CACHING', 'true');
    this.function.addEnvironment('MEMORY_CACHE_ENABLED', cacheConfig.memoryCache ? 'true' : 'false');
    this.function.addEnvironment('CACHE_DEFAULT_TTL', (cacheConfig.defaultTtl || 3600).toString());

    if (cacheConfig.enableRedis && cacheConfig.redisUrl) {
      this.function.addEnvironment('REDIS_URL', cacheConfig.redisUrl);
      this.function.addEnvironment('REDIS_ENABLED', 'true');
    }
  }

  public addBatchProcessing(batchConfig: {
    maxBatchSize?: number;
    maxWaitTime?: number;
    enableBatching?: boolean;
  }): void {
    // Configure batch processing
    this.function.addEnvironment('ENABLE_BATCH_PROCESSING', 
      (batchConfig.enableBatching !== false).toString());
    this.function.addEnvironment('MAX_BATCH_SIZE', 
      (batchConfig.maxBatchSize || 10).toString());
    this.function.addEnvironment('MAX_BATCH_WAIT_TIME', 
      (batchConfig.maxWaitTime || 1.0).toString());
  }

  public createLoadTestConfiguration(): {
    concurrencyTarget: number;
    memoryOptimized: number;
    timeoutOptimized: cdk.Duration;
  } {
    // Return optimized configuration for load testing
    const functionType = this.determineFunctionType(this.function.functionName);
    
    switch (functionType) {
      case 'orchestrator':
        return {
          concurrencyTarget: 50,
          memoryOptimized: 1536,
          timeoutOptimized: cdk.Duration.seconds(60)
        };
      case 'document-processing':
        return {
          concurrencyTarget: 20,
          memoryOptimized: 3008,
          timeoutOptimized: cdk.Duration.seconds(120)
        };
      case 'web-search':
        return {
          concurrencyTarget: 100,
          memoryOptimized: 768,
          timeoutOptimized: cdk.Duration.seconds(30)
        };
      case 'code-execution':
        return {
          concurrencyTarget: 30,
          memoryOptimized: 2048,
          timeoutOptimized: cdk.Duration.seconds(90)
        };
      default:
        return {
          concurrencyTarget: 50,
          memoryOptimized: 1024,
          timeoutOptimized: cdk.Duration.seconds(45)
        };
    }
  }
}