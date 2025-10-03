import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export interface MonitoringConstructProps {
  lambdaFunctions: lambda.Function[];
  apiGateway: apigateway.RestApi;
  alertEmail?: string;
}

export class MonitoringConstruct extends Construct {
  public readonly alarmTopic: sns.Topic;
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: MonitoringConstructProps) {
    super(scope, id);

    // SNS Topic for alerts
    this.alarmTopic = new sns.Topic(this, 'AgentScholarAlarms', {
      topicName: 'agent-scholar-alarms',
      displayName: 'Agent Scholar System Alerts'
    });

    // Email subscription if provided
    if (props.alertEmail) {
      this.alarmTopic.addSubscription(
        new subscriptions.EmailSubscription(props.alertEmail)
      );
    }

    // Create CloudWatch Dashboard
    this.dashboard = new cloudwatch.Dashboard(this, 'AgentScholarDashboard', {
      dashboardName: 'agent-scholar-monitoring',
      defaultInterval: cdk.Duration.hours(1)
    });

    // Add Lambda function monitoring
    this.addLambdaMonitoring(props.lambdaFunctions);

    // Add API Gateway monitoring
    this.addApiGatewayMonitoring(props.apiGateway);

    // Add custom metrics monitoring
    this.addCustomMetricsMonitoring();

    // Create composite alarms
    this.createCompositeAlarms();
  }

  private addLambdaMonitoring(functions: lambda.Function[]) {
    const lambdaWidgets: cloudwatch.IWidget[] = [];

    functions.forEach((func, index) => {
      const functionName = func.functionName;

      // Error Rate Alarm
      const errorRateAlarm = new cloudwatch.Alarm(this, `${functionName}ErrorRate`, {
        alarmName: `${functionName}-error-rate`,
        alarmDescription: `High error rate for ${functionName}`,
        metric: func.metricErrors({
          period: cdk.Duration.minutes(5),
          statistic: 'Sum'
        }),
        threshold: 5,
        evaluationPeriods: 2,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
      });
      errorRateAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));

      // Duration Alarm
      const durationAlarm = new cloudwatch.Alarm(this, `${functionName}Duration`, {
        alarmName: `${functionName}-duration`,
        alarmDescription: `High duration for ${functionName}`,
        metric: func.metricDuration({
          period: cdk.Duration.minutes(5),
          statistic: 'Average'
        }),
        threshold: 30000, // 30 seconds
        evaluationPeriods: 3,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
      });
      durationAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));

      // Throttle Alarm
      const throttleAlarm = new cloudwatch.Alarm(this, `${functionName}Throttles`, {
        alarmName: `${functionName}-throttles`,
        alarmDescription: `Throttling detected for ${functionName}`,
        metric: func.metricThrottles({
          period: cdk.Duration.minutes(5),
          statistic: 'Sum'
        }),
        threshold: 1,
        evaluationPeriods: 1,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
      });
      throttleAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));

      // Add widgets to dashboard
      lambdaWidgets.push(
        new cloudwatch.GraphWidget({
          title: `${functionName} - Invocations & Errors`,
          left: [func.metricInvocations()],
          right: [func.metricErrors()],
          width: 12,
          height: 6
        }),
        new cloudwatch.GraphWidget({
          title: `${functionName} - Duration & Throttles`,
          left: [func.metricDuration()],
          right: [func.metricThrottles()],
          width: 12,
          height: 6
        })
      );
    });

    // Add Lambda widgets to dashboard
    this.dashboard.addWidgets(...lambdaWidgets);
  }

  private addApiGatewayMonitoring(api: apigateway.RestApi) {
    // API Gateway Error Rate Alarm
    const apiErrorAlarm = new cloudwatch.Alarm(this, 'ApiGatewayErrors', {
      alarmName: 'agent-scholar-api-errors',
      alarmDescription: 'High error rate in API Gateway',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: '4XXError',
        dimensionsMap: {
          ApiName: api.restApiName
        },
        period: cdk.Duration.minutes(5),
        statistic: 'Sum'
      }),
      threshold: 10,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });
    apiErrorAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // API Gateway Latency Alarm
    const apiLatencyAlarm = new cloudwatch.Alarm(this, 'ApiGatewayLatency', {
      alarmName: 'agent-scholar-api-latency',
      alarmDescription: 'High latency in API Gateway',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: 'Latency',
        dimensionsMap: {
          ApiName: api.restApiName
        },
        period: cdk.Duration.minutes(5),
        statistic: 'Average'
      }),
      threshold: 10000, // 10 seconds
      evaluationPeriods: 3,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });
    apiLatencyAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // Add API Gateway widgets
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Gateway - Requests & Errors',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Count',
            dimensionsMap: { ApiName: api.restApiName }
          })
        ],
        right: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: '4XXError',
            dimensionsMap: { ApiName: api.restApiName }
          }),
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: '5XXError',
            dimensionsMap: { ApiName: api.restApiName }
          })
        ],
        width: 12,
        height: 6
      }),
      new cloudwatch.GraphWidget({
        title: 'API Gateway - Latency',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Latency',
            dimensionsMap: { ApiName: api.restApiName }
          }),
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'IntegrationLatency',
            dimensionsMap: { ApiName: api.restApiName }
          })
        ],
        width: 12,
        height: 6
      })
    );
  }

  private addCustomMetricsMonitoring() {
    // Custom metrics for Agent Scholar specific monitoring
    const customMetrics = [
      {
        name: 'AgentInvocations',
        description: 'Number of Bedrock Agent invocations'
      },
      {
        name: 'DocumentsProcessed',
        description: 'Number of documents processed'
      },
      {
        name: 'SearchQueries',
        description: 'Number of search queries executed'
      },
      {
        name: 'CodeExecutions',
        description: 'Number of code executions'
      },
      {
        name: 'AnalysisOperations',
        description: 'Number of cross-library analysis operations'
      }
    ];

    const customWidgets: cloudwatch.IWidget[] = [];

    customMetrics.forEach(metric => {
      const metricObj = new cloudwatch.Metric({
        namespace: 'AgentScholar',
        metricName: metric.name,
        period: cdk.Duration.minutes(5),
        statistic: 'Sum'
      });

      customWidgets.push(
        new cloudwatch.SingleValueWidget({
          title: metric.description,
          metrics: [metricObj],
          width: 6,
          height: 6
        })
      );
    });

    // Add custom metrics widgets
    this.dashboard.addWidgets(...customWidgets);

    // Create alarms for critical custom metrics
    const agentInvocationAlarm = new cloudwatch.Alarm(this, 'AgentInvocationFailures', {
      alarmName: 'agent-scholar-invocation-failures',
      alarmDescription: 'High failure rate in agent invocations',
      metric: new cloudwatch.Metric({
        namespace: 'AgentScholar',
        metricName: 'AgentInvocationFailures',
        period: cdk.Duration.minutes(5),
        statistic: 'Sum'
      }),
      threshold: 5,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });
    agentInvocationAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
  }

  private createCompositeAlarms() {
    // System Health Composite Alarm
    const systemHealthAlarm = new cloudwatch.CompositeAlarm(this, 'SystemHealthAlarm', {
      alarmName: 'agent-scholar-system-health',
      alarmDescription: 'Overall system health alarm',
      compositeAlarmRule: cloudwatch.AlarmRule.anyOf(
        cloudwatch.AlarmRule.fromAlarm(
          cloudwatch.Alarm.fromAlarmArn(this, 'ApiErrorRef', 
            `arn:aws:cloudwatch:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:alarm:agent-scholar-api-errors`
          ),
          cloudwatch.AlarmState.ALARM
        )
      ),
      actionsEnabled: true
    });

    systemHealthAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
  }

  public addLogInsights() {
    // Create Log Insights queries for common debugging scenarios
    const logInsightsQueries = [
      {
        name: 'Error Analysis',
        query: `
          fields @timestamp, @message, @logStream
          | filter @message like /ERROR/
          | sort @timestamp desc
          | limit 100
        `
      },
      {
        name: 'Performance Analysis',
        query: `
          fields @timestamp, @duration, @requestId
          | filter @type = "REPORT"
          | sort @duration desc
          | limit 50
        `
      },
      {
        name: 'Agent Invocation Tracking',
        query: `
          fields @timestamp, @message
          | filter @message like /agent invocation/
          | sort @timestamp desc
          | limit 100
        `
      }
    ];

    // Add Log Insights widgets to dashboard
    logInsightsQueries.forEach(query => {
      this.dashboard.addWidgets(
        new cloudwatch.LogQueryWidget({
          title: query.name,
          logGroups: [
            logs.LogGroup.fromLogGroupName(this, `${query.name}LogGroup`, '/aws/lambda/agent-scholar-orchestrator')
          ],
          queryString: query.query,
          width: 24,
          height: 6
        })
      );
    });
  }
}