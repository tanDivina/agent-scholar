#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AgentScholarStack } from './stacks/agent-scholar-stack';

const app = new cdk.App();

// Get environment configuration
const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION || 'us-east-1';

// Create the main Agent Scholar stack
new AgentScholarStack(app, 'AgentScholarStack', {
  env: {
    account: account,
    region: region,
  },
  description: 'Agent Scholar - Autonomous AI research and analysis agent',
  tags: {
    Project: 'AgentScholar',
    Environment: 'production',
    ManagedBy: 'CDK'
  }
});

app.synth();