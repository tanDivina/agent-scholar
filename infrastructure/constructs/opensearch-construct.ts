import * as cdk from 'aws-cdk-lib';
import * as opensearch from 'aws-cdk-lib/aws-opensearchserverless';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface OpenSearchConstructProps {
  collectionName: string;
  indexName: string;
}

export class OpenSearchConstruct extends Construct {
  public readonly collection: opensearch.CfnCollection;
  public readonly collectionEndpoint: string;
  public readonly indexName: string;

  constructor(scope: Construct, id: string, props: OpenSearchConstructProps) {
    super(scope, id);

    // Create encryption policy for the collection
    const encryptionPolicy = new opensearch.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `${props.collectionName}-encryption-policy`,
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [
          {
            Resource: [`collection/${props.collectionName}`],
            ResourceType: 'collection'
          }
        ],
        AWSOwnedKey: true
      })
    });

    // Create network policy for the collection
    const networkPolicy = new opensearch.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `${props.collectionName}-network-policy`,
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            {
              Resource: [`collection/${props.collectionName}`],
              ResourceType: 'collection'
            }
          ],
          AllowFromPublic: true
        }
      ])
    });

    // Create the OpenSearch Serverless collection
    this.collection = new opensearch.CfnCollection(this, 'Collection', {
      name: props.collectionName,
      type: 'VECTORSEARCH',
      description: 'Vector search collection for Agent Scholar document embeddings'
    });

    // Add dependencies
    this.collection.addDependency(encryptionPolicy);
    this.collection.addDependency(networkPolicy);

    // Store collection endpoint and index name
    this.collectionEndpoint = this.collection.attrCollectionEndpoint;
    this.indexName = props.indexName;

    // Output the collection endpoint
    new cdk.CfnOutput(this, 'CollectionEndpoint', {
      value: this.collectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint'
    });

    new cdk.CfnOutput(this, 'CollectionName', {
      value: props.collectionName,
      description: 'OpenSearch Serverless collection name'
    });
  }

  /**
   * Create IAM policy for accessing this OpenSearch collection
   */
  public createAccessPolicy(principals: iam.IPrincipal[]): opensearch.CfnAccessPolicy {
    const principalArns = principals.map(p => p.principalArn);
    
    return new opensearch.CfnAccessPolicy(this, 'AccessPolicy', {
      name: `${this.collection.name}-access-policy`,
      type: 'data',
      policy: JSON.stringify([
        {
          Rules: [
            {
              Resource: [`collection/${this.collection.name}`],
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DeleteCollectionItems',
                'aoss:UpdateCollectionItems',
                'aoss:DescribeCollectionItems'
              ],
              ResourceType: 'collection'
            },
            {
              Resource: [`index/${this.collection.name}/*`],
              Permission: [
                'aoss:CreateIndex',
                'aoss:DeleteIndex',
                'aoss:UpdateIndex',
                'aoss:DescribeIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument'
              ],
              ResourceType: 'index'
            }
          ],
          Principal: principalArns
        }
      ])
    });
  }
}