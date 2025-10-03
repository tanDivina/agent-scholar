import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface CognitoConstructProps {
  domainPrefix?: string;
  enableMfa?: boolean;
  passwordPolicy?: cognito.PasswordPolicy;
}

export class CognitoConstruct extends Construct {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly userPoolDomain: cognito.UserPoolDomain;
  public readonly identityPool: cognito.CfnIdentityPool;
  public readonly authenticatedRole: iam.Role;
  public readonly unauthenticatedRole: iam.Role;

  constructor(scope: Construct, id: string, props: CognitoConstructProps = {}) {
    super(scope, id);

    // Create User Pool
    this.userPool = new cognito.UserPool(this, 'AgentScholarUserPool', {
      userPoolName: 'agent-scholar-users',
      selfSignUpEnabled: true,
      signInAliases: {
        email: true,
        username: true
      },
      autoVerify: {
        email: true
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true
        },
        givenName: {
          required: true,
          mutable: true
        },
        familyName: {
          required: true,
          mutable: true
        }
      },
      customAttributes: {
        'subscription_tier': new cognito.StringAttribute({
          minLen: 1,
          maxLen: 20,
          mutable: true
        }),
        'api_quota': new cognito.NumberAttribute({
          min: 0,
          max: 100000,
          mutable: true
        })
      },
      passwordPolicy: props.passwordPolicy || {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
        tempPasswordValidity: cdk.Duration.days(7)
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      mfa: props.enableMfa ? cognito.Mfa.REQUIRED : cognito.Mfa.OPTIONAL,
      mfaSecondFactor: {
        sms: true,
        otp: true
      },
      deviceTracking: {
        challengeRequiredOnNewDevice: true,
        deviceOnlyRememberedOnUserPrompt: false
      },
      lambdaTriggers: {
        preSignUp: this.createPreSignUpTrigger(),
        postConfirmation: this.createPostConfirmationTrigger(),
        preAuthentication: this.createPreAuthenticationTrigger()
      }
    });

    // Create User Pool Client
    this.userPoolClient = new cognito.UserPoolClient(this, 'AgentScholarUserPoolClient', {
      userPool: this.userPool,
      userPoolClientName: 'agent-scholar-client',
      generateSecret: false, // For web applications
      authFlows: {
        userPassword: true,
        userSrp: true,
        custom: true,
        adminUserPassword: true
      },
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: true
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
          cognito.OAuthScope.custom('agent-scholar/read'),
          cognito.OAuthScope.custom('agent-scholar/write')
        ],
        callbackUrls: [
          'http://localhost:8501/callback',
          'https://your-domain.com/callback'
        ],
        logoutUrls: [
          'http://localhost:8501/logout',
          'https://your-domain.com/logout'
        ]
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO
      ],
      readAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({
          email: true,
          givenName: true,
          familyName: true,
          emailVerified: true
        })
        .withCustomAttributes('subscription_tier', 'api_quota'),
      writeAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({
          email: true,
          givenName: true,
          familyName: true
        })
        .withCustomAttributes('subscription_tier', 'api_quota'),
      tokenValidity: {
        accessToken: cdk.Duration.hours(1),
        idToken: cdk.Duration.hours(1),
        refreshToken: cdk.Duration.days(30)
      },
      refreshTokenValidity: cdk.Duration.days(30),
      preventUserExistenceErrors: true
    });

    // Create User Pool Domain
    this.userPoolDomain = new cognito.UserPoolDomain(this, 'AgentScholarUserPoolDomain', {
      userPool: this.userPool,
      cognitoDomain: {
        domainPrefix: props.domainPrefix || 'agent-scholar-auth'
      }
    });

    // Create Identity Pool for AWS resource access
    this.identityPool = new cognito.CfnIdentityPool(this, 'AgentScholarIdentityPool', {
      identityPoolName: 'agent-scholar-identity',
      allowUnauthenticatedIdentities: true,
      cognitoIdentityProviders: [{
        clientId: this.userPoolClient.userPoolClientId,
        providerName: this.userPool.userPoolProviderName,
        serverSideTokenCheck: true
      }]
    });

    // Create IAM roles for authenticated and unauthenticated users
    this.authenticatedRole = new iam.Role(this, 'AuthenticatedRole', {
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'authenticated'
          }
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
      inlinePolicies: {
        AuthenticatedUserPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'execute-api:Invoke'
              ],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cognito-identity.amazonaws.com:aud': this.identityPool.ref
                }
              }
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:PutObject'
              ],
              resources: ['arn:aws:s3:::agent-scholar-documents/*'],
              conditions: {
                StringLike: {
                  's3:prefix': ['${cognito-identity.amazonaws.com:sub}/*']
                }
              }
            })
          ]
        })
      }
    });

    this.unauthenticatedRole = new iam.Role(this, 'UnauthenticatedRole', {
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'unauthenticated'
          }
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
      inlinePolicies: {
        UnauthenticatedUserPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'execute-api:Invoke'
              ],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cognito-identity.amazonaws.com:aud': this.identityPool.ref
                }
              }
            })
          ]
        })
      }
    });

    // Attach roles to identity pool
    new cognito.CfnIdentityPoolRoleAttachment(this, 'IdentityPoolRoleAttachment', {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: this.authenticatedRole.roleArn,
        unauthenticated: this.unauthenticatedRole.roleArn
      }
    });

    // Output important values
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID'
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID'
    });

    new cdk.CfnOutput(this, 'IdentityPoolId', {
      value: this.identityPool.ref,
      description: 'Cognito Identity Pool ID'
    });

    new cdk.CfnOutput(this, 'UserPoolDomainUrl', {
      value: `https://${this.userPoolDomain.domainName}.auth.${cdk.Stack.of(this).region}.amazoncognito.com`,
      description: 'Cognito User Pool Domain URL'
    });
  }

  private createPreSignUpTrigger(): lambda.Function {
    return new lambda.Function(this, 'PreSignUpTrigger', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Pre-signup trigger: {json.dumps(event)}")
    
    # Auto-confirm user and set default attributes
    event['response']['autoConfirmUser'] = True
    event['response']['autoVerifyEmail'] = True
    
    # Set default subscription tier
    if 'clientMetadata' not in event['request']:
        event['request']['clientMetadata'] = {}
    
    # Set default custom attributes
    event['response']['userAttributes'] = {
        'custom:subscription_tier': 'free',
        'custom:api_quota': '100'
    }
    
    return event
      `),
      timeout: cdk.Duration.seconds(30)
    });
  }

  private createPostConfirmationTrigger(): lambda.Function {
    return new lambda.Function(this, 'PostConfirmationTrigger', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Post-confirmation trigger: {json.dumps(event)}")
    
    # Log successful user confirmation
    user_id = event['request']['userAttributes']['sub']
    email = event['request']['userAttributes']['email']
    
    logger.info(f"User confirmed: {user_id} ({email})")
    
    # Here you could add logic to:
    # - Send welcome email
    # - Initialize user data
    # - Set up user-specific resources
    
    return event
      `),
      timeout: cdk.Duration.seconds(30)
    });
  }

  private createPreAuthenticationTrigger(): lambda.Function {
    return new lambda.Function(this, 'PreAuthenticationTrigger', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Pre-authentication trigger: {json.dumps(event)}")
    
    # Add any pre-authentication logic here
    # For example, check if user is allowed to authenticate
    
    user_id = event['request']['userAttributes']['sub']
    email = event['request']['userAttributes']['email']
    
    logger.info(f"Authentication attempt: {user_id} ({email})")
    
    # You could add logic to:
    # - Check if account is suspended
    # - Implement additional security checks
    # - Log authentication attempts
    
    return event
      `),
      timeout: cdk.Duration.seconds(30)
    });
  }
}