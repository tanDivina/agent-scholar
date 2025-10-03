import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as applicationautoscaling from 'aws-cdk-lib/aws-applicationautoscaling';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface AutoScalingConstructProps {
  lambdaFunctions: lambda.Function[];
  apiGateway?: cdk.aws_apigateway.RestApi;
  alertEmail?: string;
  scalingPolicies?: {
    targetUtilization?: number;
    scaleUpCooldown?: cdk.Duration;
    scaleDownCooldown?: cdk.Duration;
    minCapacity?: number;
    maxCapacity?: number;
  };
}

export class AutoScalingConstruct extends Construct {
  public readonly scalingTargets: applicationautoscaling.ScalableTarget[];
  public readonly alarmTopic: sns.Topic;
  public readonly dashboard: cloudwatch.Dashboard;
  public readonly scalingPolicies: applicationautoscaling.StepScalingPolicy[];

  constructor(scope: Construct, id: string, props: AutoScalingConstructProps) {
    super(scope, id);

    // Default scaling configuration
    const scalingConfig = {
      targetUtilization: props.scalingPolicies?.targetUtilization || 70,
      scaleUpCooldown: props.scalingPolicies?.scaleUpCooldown || cdk.Duration.minutes(2),
      scaleDownCooldown: props.scalingPolicies?.scaleDownCooldown || cdk.Duration.minutes(5),
      minCapacity: props.scalingPolicies?.minCapacity || 1,
      maxCapacity: props.scalingPolicies?.maxCapacity || 100
    };

    // Create SNS topic for scaling alerts
    this.alarmTopic = new sns.Topic(this, 'ScalingAlarmTopic', {
      topicName: 'agent-scholar-scaling-alerts',
      displayName: 'Agent Scholar Auto-Scaling Alerts'
    });

    if (props.alertEmail) {
      this.alarmTopic.addSubscription(
        new subscriptions.EmailSubscription(props.alertEmail)
      );
    }

    // Initialize arrays
    this.scalingTargets = [];
    this.scalingPolicies = [];

    // Configure Lambda function scaling
    props.lambdaFunctions.forEach((lambdaFunction, index) => {
      this.configureLambdaScaling(lambdaFunction, scalingConfig, index);
    });

    // Configure API Gateway scaling if provided
    if (props.apiGateway) {
      this.configureApiGatewayScaling(props.apiGateway, scalingConfig);
    }

    // Create CloudWatch dashboard
    this.dashboard = this.createPerformanceDashboard(props.lambdaFunctions, props.apiGateway);

    // Create custom metrics and alarms
    this.createCustomMetricsAndAlarms(props.lambdaFunctions);

    // Output important information
    new cdk.CfnOutput(this, 'ScalingTopicArn', {
      value: this.alarmTopic.topicArn,
      description: 'SNS Topic ARN for scaling alerts'
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${cdk.Stack.of(this).region}.console.aws.amazon.com/cloudwatch/home?region=${cdk.Stack.of(this).region}#dashboards:name=${this.dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL'
    });
  }

  private configureLambdaScaling(
    lambdaFunction: lambda.Function,
    scalingConfig: any,
    index: number
  ): void {
    // Create scalable target for Lambda provisioned concurrency
    const scalableTarget = new applicationautoscaling.ScalableTarget(this, `ScalableTarget${index}`, {
      serviceNamespace: applicationautoscaling.ServiceNamespace.LAMBDA,
      resourceId: `function:${lambdaFunction.functionName}:provisioned`,
      scalableDimension: 'lambda:function:ProvisionedConcurrencyUtilization',
      minCapacity: scalingConfig.minCapacity,
      maxCapacity: scalingConfig.maxCapacity,
      role: this.createScalingRole()
    });

    this.scalingTargets.push(scalableTarget);

    // Create target tracking scaling policy based on utilization
    const utilizationPolicy = new applicationautoscaling.TargetTrackingScalingPolicy(this, `UtilizationPolicy${index}`, {
      scalingTarget: scalableTarget,
      targetValue: scalingConfig.targetUtilization,
      predefinedMetric: applicationautoscaling.PredefinedMetric.LAMBDA_PROVISIONED_CONCURRENCY_UTILIZATION,
      scaleInCooldown: scalingConfig.scaleDownCooldown,
      scaleOutCooldown: scalingConfig.scaleUpCooldown
    });

    // Create step scaling policy for rapid scale-up under high load
    const stepScalingPolicy = new applicationautoscaling.StepScalingPolicy(this, `StepScalingPolicy${index}`, {
      scalingTarget: scalableTarget,
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Lambda',
        metricName: 'ConcurrentExecutions',
        dimensionsMap: {
          FunctionName: lambdaFunction.functionName
        },
        statistic: 'Average'
      }),
      scalingSteps: [
        { upper: 50, change: +2 },   // Add 2 when concurrent executions < 50
        { lower: 50, upper: 100, change: +5 }, // Add 5 when 50 <= concurrent executions < 100
        { lower: 100, change: +10 }  // Add 10 when concurrent executions >= 100
      ],
      adjustmentType: applicationautoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
      cooldown: scalingConfig.scaleUpCooldown,
      evaluationPeriods: 2,
      datapointsToAlarm: 2
    });

    this.scalingPolicies.push(stepScalingPolicy);

    // Create alarms for Lambda function performance
    this.createLambdaAlarms(lambdaFunction, index);
  }

  private configureApiGatewayScaling(
    apiGateway: cdk.aws_apigateway.RestApi,
    scalingConfig: any
  ): void {
    // Create CloudWatch alarms for API Gateway
    const highLatencyAlarm = new cloudwatch.Alarm(this, 'ApiGatewayHighLatency', {
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: 'Latency',
        dimensionsMap: {
          ApiName: apiGateway.restApiName
        },
        statistic: 'Average'
      }),
      threshold: 5000, // 5 seconds
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'API Gateway latency is high'
    });

    highLatencyAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );

    const highErrorRateAlarm = new cloudwatch.Alarm(this, 'ApiGatewayHighErrorRate', {
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: '4XXError',
        dimensionsMap: {
          ApiName: apiGateway.restApiName
        },
        statistic: 'Sum'
      }),
      threshold: 10, // 10 errors in 5 minutes
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'API Gateway error rate is high'
    });

    highErrorRateAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );
  }

  private createLambdaAlarms(lambdaFunction: lambda.Function, index: number): void {
    // High duration alarm
    const highDurationAlarm = new cloudwatch.Alarm(this, `HighDurationAlarm${index}`, {
      metric: lambdaFunction.metricDuration({
        statistic: 'Average'
      }),
      threshold: 10000, // 10 seconds
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: `${lambdaFunction.functionName} duration is high`
    });

    highDurationAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );

    // High error rate alarm
    const highErrorRateAlarm = new cloudwatch.Alarm(this, `HighErrorRateAlarm${index}`, {
      metric: lambdaFunction.metricErrors({
        statistic: 'Sum'
      }),
      threshold: 5, // 5 errors in 5 minutes
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: `${lambdaFunction.functionName} error rate is high`
    });

    highErrorRateAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );

    // High throttle alarm
    const highThrottleAlarm = new cloudwatch.Alarm(this, `HighThrottleAlarm${index}`, {
      metric: lambdaFunction.metricThrottles({
        statistic: 'Sum'
      }),
      threshold: 1, // Any throttling
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: `${lambdaFunction.functionName} is being throttled`
    });

    highThrottleAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );

    // Memory utilization alarm (custom metric)
    const memoryUtilizationAlarm = new cloudwatch.Alarm(this, `MemoryUtilizationAlarm${index}`, {
      metric: new cloudwatch.Metric({
        namespace: 'AgentScholar/Performance',
        metricName: 'MemoryUtilization',
        dimensionsMap: {
          FunctionName: lambdaFunction.functionName
        },
        statistic: 'Average'
      }),
      threshold: 80, // 80% memory utilization
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: `${lambdaFunction.functionName} memory utilization is high`
    });

    memoryUtilizationAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );
  }

  private createCustomMetricsAndAlarms(lambdaFunctions: lambda.Function[]): void {
    // Create custom metrics for system-wide performance
    const systemThroughputAlarm = new cloudwatch.Alarm(this, 'SystemThroughputAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'AgentScholar/Performance',
        metricName: 'SystemThroughput',
        statistic: 'Average'
      }),
      threshold: 0.1, // Less than 0.1 RPS
      evaluationPeriods: 5,
      datapointsToAlarm: 3,
      treatMissingData: cloudwatch.TreatMissingData.BREACHING,
      alarmDescription: 'System throughput is critically low',
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
    });

    systemThroughputAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );

    // Cache hit rate alarm
    const cacheHitRateAlarm = new cloudwatch.Alarm(this, 'CacheHitRateAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'AgentScholar/Performance',
        metricName: 'CacheHitRate',
        statistic: 'Average'
      }),
      threshold: 30, // Less than 30% hit rate
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Cache hit rate is low',
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
    });

    cacheHitRateAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );
  }

  private createPerformanceDashboard(
    lambdaFunctions: lambda.Function[],
    apiGateway?: cdk.aws_apigateway.RestApi
  ): cloudwatch.Dashboard {
    const dashboard = new cloudwatch.Dashboard(this, 'PerformanceDashboard', {
      dashboardName: 'agent-scholar-performance',
      defaultInterval: cdk.Duration.hours(1)
    });

    // System overview row
    const systemOverviewWidgets = [
      new cloudwatch.GraphWidget({
        title: 'System Throughput',
        left: [
          new cloudwatch.Metric({
            namespace: 'AgentScholar/Performance',
            metricName: 'SystemThroughput',
            statistic: 'Average'
          })
        ],
        width: 8,
        height: 6
      }),
      new cloudwatch.SingleValueWidget({
        title: 'Cache Hit Rate',
        metrics: [
          new cloudwatch.Metric({
            namespace: 'AgentScholar/Performance',
            metricName: 'CacheHitRate',
            statistic: 'Average'
          })
        ],
        width: 8,
        height: 6
      }),
      new cloudwatch.SingleValueWidget({
        title: 'Average Response Time',
        metrics: [
          new cloudwatch.Metric({
            namespace: 'AgentScholar/Performance',
            metricName: 'AverageResponseTime',
            statistic: 'Average'
          })
        ],
        width: 8,
        height: 6
      })
    ];

    dashboard.addWidgets(...systemOverviewWidgets);

    // Lambda functions performance row
    const lambdaWidgets = lambdaFunctions.map((func, index) => {
      return new cloudwatch.GraphWidget({
        title: `${func.functionName} Performance`,
        left: [
          func.metricDuration({ statistic: 'Average', label: 'Duration' }),
          func.metricInvocations({ statistic: 'Sum', label: 'Invocations' })
        ],
        right: [
          func.metricErrors({ statistic: 'Sum', label: 'Errors' }),
          func.metricThrottles({ statistic: 'Sum', label: 'Throttles' })
        ],
        width: 12,
        height: 6
      });
    });

    if (lambdaWidgets.length > 0) {
      dashboard.addWidgets(...lambdaWidgets);
    }

    // API Gateway performance row (if provided)
    if (apiGateway) {
      const apiGatewayWidgets = [
        new cloudwatch.GraphWidget({
          title: 'API Gateway Performance',
          left: [
            new cloudwatch.Metric({
              namespace: 'AWS/ApiGateway',
              metricName: 'Count',
              dimensionsMap: { ApiName: apiGateway.restApiName },
              statistic: 'Sum',
              label: 'Requests'
            }),
            new cloudwatch.Metric({
              namespace: 'AWS/ApiGateway',
              metricName: 'Latency',
              dimensionsMap: { ApiName: apiGateway.restApiName },
              statistic: 'Average',
              label: 'Latency'
            })
          ],
          right: [
            new cloudwatch.Metric({
              namespace: 'AWS/ApiGateway',
              metricName: '4XXError',
              dimensionsMap: { ApiName: apiGateway.restApiName },
              statistic: 'Sum',
              label: '4XX Errors'
            }),
            new cloudwatch.Metric({
              namespace: 'AWS/ApiGateway',
              metricName: '5XXError',
              dimensionsMap: { ApiName: apiGateway.restApiName },
              statistic: 'Sum',
              label: '5XX Errors'
            })
          ],
          width: 24,
          height: 6
        })
      ];

      dashboard.addWidgets(...apiGatewayWidgets);
    }

    // Resource utilization row
    const resourceWidgets = [
      new cloudwatch.GraphWidget({
        title: 'Memory Utilization',
        left: lambdaFunctions.map(func => 
          new cloudwatch.Metric({
            namespace: 'AgentScholar/Performance',
            metricName: 'MemoryUtilization',
            dimensionsMap: { FunctionName: func.functionName },
            statistic: 'Average',
            label: func.functionName
          })
        ),
        width: 12,
        height: 6
      }),
      new cloudwatch.GraphWidget({
        title: 'Concurrent Executions',
        left: lambdaFunctions.map(func => 
          new cloudwatch.Metric({
            namespace: 'AWS/Lambda',
            metricName: 'ConcurrentExecutions',
            dimensionsMap: { FunctionName: func.functionName },
            statistic: 'Maximum',
            label: func.functionName
          })
        ),
        width: 12,
        height: 6
      })
    ];

    dashboard.addWidgets(...resourceWidgets);

    return dashboard;
  }

  private createScalingRole(): iam.Role {
    return new iam.Role(this, 'AutoScalingRole', {
      assumedBy: new iam.ServicePrincipal('application-autoscaling.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/ApplicationAutoScalingLambdaConcurrencyPolicy')
      ],
      inlinePolicies: {
        LambdaScalingPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'lambda:PutProvisionedConcurrencyConfig',
                'lambda:GetProvisionedConcurrencyConfig',
                'lambda:DeleteProvisionedConcurrencyConfig'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cloudwatch:PutMetricData',
                'cloudwatch:GetMetricStatistics',
                'cloudwatch:ListMetrics'
              ],
              resources: ['*']
            })
          ]
        })
      }
    });
  }

  public addCustomScalingPolicy(
    target: applicationautoscaling.ScalableTarget,
    metricName: string,
    namespace: string,
    threshold: number,
    scaleUpChange: number,
    scaleDownChange: number
  ): applicationautoscaling.StepScalingPolicy {
    const customPolicy = new applicationautoscaling.StepScalingPolicy(this, `CustomPolicy${metricName}`, {
      scalingTarget: target,
      metric: new cloudwatch.Metric({
        namespace: namespace,
        metricName: metricName,
        statistic: 'Average'
      }),
      scalingSteps: [
        { upper: threshold, change: scaleDownChange },
        { lower: threshold, change: scaleUpChange }
      ],
      adjustmentType: applicationautoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
      cooldown: cdk.Duration.minutes(3),
      evaluationPeriods: 2,
      datapointsToAlarm: 1
    });

    this.scalingPolicies.push(customPolicy);
    return customPolicy;
  }

  public createLoadTestingAlarms(): void {
    // Create alarms specifically for load testing scenarios
    const loadTestAlarm = new cloudwatch.Alarm(this, 'LoadTestPerformanceAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'AgentScholar/Performance',
        metricName: 'AverageResponseTime',
        statistic: 'Average'
      }),
      threshold: 15000, // 15 seconds during load testing
      evaluationPeriods: 2,
      datapointsToAlarm: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Performance degraded during load testing'
    });

    loadTestAlarm.addAlarmAction(
      new cdk.aws_cloudwatch_actions.SnsAction(this.alarmTopic)
    );
  }
}