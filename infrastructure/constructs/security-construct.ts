import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import { Construct } from 'constructs';

export interface SecurityConstructProps {
  apiGatewayArn?: string;
  enableWaf?: boolean;
}

export class SecurityConstruct extends Construct {
  public readonly rateLimitTable: dynamodb.Table;
  public readonly encryptionKey: kms.Key;
  public readonly securityRole: iam.Role;
  public readonly webAcl?: wafv2.CfnWebACL;

  constructor(scope: Construct, id: string, props: SecurityConstructProps = {}) {
    super(scope, id);

    // Create KMS key for encryption
    this.encryptionKey = new kms.Key(this, 'AgentScholarEncryptionKey', {
      description: 'Encryption key for Agent Scholar sensitive data',
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: 'Enable IAM User Permissions',
            effect: iam.Effect.ALLOW,
            principals: [new iam.AccountRootPrincipal()],
            actions: ['kms:*'],
            resources: ['*']
          }),
          new iam.PolicyStatement({
            sid: 'Allow Lambda Functions',
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal('lambda.amazonaws.com')],
            actions: [
              'kms:Decrypt',
              'kms:DescribeKey',
              'kms:Encrypt',
              'kms:GenerateDataKey',
              'kms:ReEncrypt*'
            ],
            resources: ['*']
          })
        ]
      })
    });

    // Create alias for the key
    new kms.Alias(this, 'AgentScholarEncryptionKeyAlias', {
      aliasName: 'alias/agent-scholar-encryption',
      targetKey: this.encryptionKey
    });

    // Create DynamoDB table for rate limiting
    this.rateLimitTable = new dynamodb.Table(this, 'RateLimitTable', {
      tableName: 'agent-scholar-rate-limits',
      partitionKey: {
        name: 'identifier',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.encryptionKey,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      pointInTimeRecovery: true
    });

    // Create security role for Lambda functions
    this.securityRole = new iam.Role(this, 'SecurityRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        SecurityPolicy: new iam.PolicyDocument({
          statements: [
            // DynamoDB permissions for rate limiting
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
                'dynamodb:Scan'
              ],
              resources: [this.rateLimitTable.tableArn]
            }),
            // KMS permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'kms:Decrypt',
                'kms:DescribeKey',
                'kms:Encrypt',
                'kms:GenerateDataKey',
                'kms:ReEncrypt*'
              ],
              resources: [this.encryptionKey.keyArn]
            }),
            // SSM Parameter Store permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters',
                'ssm:GetParametersByPath'
              ],
              resources: [
                `arn:aws:ssm:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:parameter/agent-scholar/*`
              ]
            }),
            // CloudWatch permissions for security monitoring
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cloudwatch:PutMetricData',
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ],
              resources: ['*']
            }),
            // Cognito permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cognito-idp:GetUser',
                'cognito-idp:AdminGetUser',
                'cognito-identity:GetCredentialsForIdentity'
              ],
              resources: ['*']
            })
          ]
        })
      }
    });

    // Create WAF Web ACL if enabled
    if (props.enableWaf && props.apiGatewayArn) {
      this.webAcl = new wafv2.CfnWebACL(this, 'AgentScholarWebACL', {
        scope: 'REGIONAL',
        defaultAction: { allow: {} },
        name: 'agent-scholar-web-acl',
        description: 'Web ACL for Agent Scholar API Gateway',
        rules: [
          // Rate limiting rule
          {
            name: 'RateLimitRule',
            priority: 1,
            statement: {
              rateBasedStatement: {
                limit: 2000, // 2000 requests per 5 minutes
                aggregateKeyType: 'IP'
              }
            },
            action: { block: {} },
            visibilityConfig: {
              sampledRequestsEnabled: true,
              cloudWatchMetricsEnabled: true,
              metricName: 'RateLimitRule'
            }
          },
          // AWS Managed Rules - Core Rule Set
          {
            name: 'AWSManagedRulesCommonRuleSet',
            priority: 2,
            overrideAction: { none: {} },
            statement: {
              managedRuleGroupStatement: {
                vendorName: 'AWS',
                name: 'AWSManagedRulesCommonRuleSet'
              }
            },
            visibilityConfig: {
              sampledRequestsEnabled: true,
              cloudWatchMetricsEnabled: true,
              metricName: 'CommonRuleSetMetric'
            }
          },
          // AWS Managed Rules - Known Bad Inputs
          {
            name: 'AWSManagedRulesKnownBadInputsRuleSet',
            priority: 3,
            overrideAction: { none: {} },
            statement: {
              managedRuleGroupStatement: {
                vendorName: 'AWS',
                name: 'AWSManagedRulesKnownBadInputsRuleSet'
              }
            },
            visibilityConfig: {
              sampledRequestsEnabled: true,
              cloudWatchMetricsEnabled: true,
              metricName: 'KnownBadInputsRuleSetMetric'
            }
          },
          // AWS Managed Rules - SQL Injection
          {
            name: 'AWSManagedRulesSQLiRuleSet',
            priority: 4,
            overrideAction: { none: {} },
            statement: {
              managedRuleGroupStatement: {
                vendorName: 'AWS',
                name: 'AWSManagedRulesSQLiRuleSet'
              }
            },
            visibilityConfig: {
              sampledRequestsEnabled: true,
              cloudWatchMetricsEnabled: true,
              metricName: 'SQLiRuleSetMetric'
            }
          },
          // Geographic restriction (optional)
          {
            name: 'GeoRestrictionRule',
            priority: 5,
            statement: {
              geoMatchStatement: {
                countryCodes: ['CN', 'RU', 'KP'] // Block these countries
              }
            },
            action: { block: {} },
            visibilityConfig: {
              sampledRequestsEnabled: true,
              cloudWatchMetricsEnabled: true,
              metricName: 'GeoRestrictionRule'
            }
          }
        ],
        visibilityConfig: {
          sampledRequestsEnabled: true,
          cloudWatchMetricsEnabled: true,
          metricName: 'AgentScholarWebACL'
        }
      });

      // Associate Web ACL with API Gateway
      new wafv2.CfnWebACLAssociation(this, 'WebACLAssociation', {
        resourceArn: props.apiGatewayArn,
        webAclArn: this.webAcl.attrArn
      });
    }

    // Create SSM parameters for security configuration
    this.createSecurityParameters();

    // Output important values
    new cdk.CfnOutput(this, 'EncryptionKeyId', {
      value: this.encryptionKey.keyId,
      description: 'KMS Encryption Key ID'
    });

    new cdk.CfnOutput(this, 'RateLimitTableName', {
      value: this.rateLimitTable.tableName,
      description: 'Rate Limit DynamoDB Table Name'
    });

    if (this.webAcl) {
      new cdk.CfnOutput(this, 'WebACLArn', {
        value: this.webAcl.attrArn,
        description: 'WAF Web ACL ARN'
      });
    }
  }

  private createSecurityParameters(): void {
    // JWT Secret Key (in production, this should be generated securely)
    new ssm.StringParameter(this, 'JWTSecretParameter', {
      parameterName: '/agent-scholar/secrets/JWT_SECRET_KEY',
      stringValue: 'your-super-secret-jwt-key-change-in-production',
      type: ssm.ParameterType.SECURE_STRING,
      description: 'JWT Secret Key for token signing'
    });

    // API Key Hash (in production, this should be a proper hash)
    new ssm.StringParameter(this, 'APIKeyHashParameter', {
      parameterName: '/agent-scholar/secrets/API_KEY_HASH',
      stringValue: 'your-api-key-hash-change-in-production',
      type: ssm.ParameterType.SECURE_STRING,
      description: 'API Key Hash for service authentication'
    });

    // KMS Key ID parameter
    new ssm.StringParameter(this, 'KMSKeyIdParameter', {
      parameterName: '/agent-scholar/config/KMS_KEY_ID',
      stringValue: this.encryptionKey.keyId,
      type: ssm.ParameterType.STRING,
      description: 'KMS Key ID for encryption'
    });

    // Security configuration parameters
    new ssm.StringParameter(this, 'SecurityConfigParameter', {
      parameterName: '/agent-scholar/config/SECURITY_CONFIG',
      stringValue: JSON.stringify({
        rate_limits: {
          default: { requests: 100, window: 3600 },
          authenticated: { requests: 1000, window: 3600 },
          premium: { requests: 10000, window: 3600 }
        },
        password_policy: {
          min_length: 12,
          require_uppercase: true,
          require_lowercase: true,
          require_numbers: true,
          require_symbols: true,
          max_age_days: 90
        },
        session_timeout: 3600,
        max_login_attempts: 5,
        lockout_duration: 900
      }),
      type: ssm.ParameterType.STRING,
      description: 'Security configuration settings'
    });
  }
}