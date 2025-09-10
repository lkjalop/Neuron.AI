#!/usr/bin/env python3
"""
Multi-Cloud Cost Calculator for Neuron-AI
Compares deployment costs across AWS, Azure, GCP, and Alibaba Cloud
"""

import json
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, List
from datetime import datetime

@dataclass
class ResourceCosts:
    compute: float
    storage: float
    database: float
    cache: float
    networking: float
    monitoring: float
    backup: float
    
    @property
    def total(self) -> float:
        return (self.compute + self.storage + self.database + 
                self.cache + self.networking + self.monitoring + self.backup)

@dataclass
class DeploymentSize:
    name: str
    nodes: int
    node_type: str
    storage_gb: int
    database_size: str
    cache_size: str

class MultiCloudCostCalculator:
    """Calculate and compare costs across cloud providers"""
    
    def __init__(self):
        # Deployment size configurations
        self.deployment_sizes = {
            'small': DeploymentSize(
                name='Small (Dev/Test)',
                nodes=2,
                node_type='small',
                storage_gb=100,
                database_size='micro',
                cache_size='basic'
            ),
            'medium': DeploymentSize(
                name='Medium (Staging)',
                nodes=3,
                node_type='medium',
                storage_gb=200,
                database_size='small',
                cache_size='standard'
            ),
            'large': DeploymentSize(
                name='Large (Production)',
                nodes=5,
                node_type='large',
                storage_gb=500,
                database_size='medium',
                cache_size='premium'
            ),
            'enterprise': DeploymentSize(
                name='Enterprise (High-Scale)',
                nodes=10,
                node_type='xlarge',
                storage_gb=1000,
                database_size='large',
                cache_size='premium-cluster'
            )
        }
        
        # Monthly pricing data (USD) - Updated as of 2024
        self.pricing = {
            'aws': {
                'compute': {
                    'small': 35,    # t3.medium
                    'medium': 45,   # t3.large
                    'large': 90,    # t3.xlarge
                    'xlarge': 180   # t3.2xlarge
                },
                'storage_per_gb': 0.08,  # EBS gp3
                'database': {
                    'micro': 12,    # db.t3.micro
                    'small': 25,    # db.t3.small
                    'medium': 50,   # db.t3.medium
                    'large': 100    # db.t3.large
                },
                'cache': {
                    'basic': 15,           # cache.t3.micro
                    'standard': 30,        # cache.t3.small
                    'premium': 60,         # cache.t3.medium
                    'premium-cluster': 120 # Multi-AZ
                },
                'networking': 25,  # ALB + data transfer
                'monitoring': 10,  # CloudWatch
                'backup': 5       # S3 backups
            },
            'azure': {
                'compute': {
                    'small': 40,    # Standard_B2s
                    'medium': 55,   # Standard_B4ms
                    'large': 110,   # Standard_D4s_v3
                    'xlarge': 220   # Standard_D8s_v3
                },
                'storage_per_gb': 0.12,  # Premium SSD
                'database': {
                    'micro': 18,    # B_Standard_B1ms
                    'small': 35,    # B_Standard_B2s
                    'medium': 70,   # GP_Gen5_2
                    'large': 140    # GP_Gen5_4
                },
                'cache': {
                    'basic': 20,           # Basic C0
                    'standard': 40,        # Basic C1
                    'premium': 80,         # Standard C2
                    'premium-cluster': 160 # Premium cluster
                },
                'networking': 30,  # Load Balancer
                'monitoring': 15,  # Azure Monitor
                'backup': 8       # Azure Backup
            },
            'gcp': {
                'compute': {
                    'small': 32,    # e2-medium
                    'medium': 48,   # e2-standard-2
                    'large': 96,    # e2-standard-4
                    'xlarge': 192   # e2-standard-8
                },
                'storage_per_gb': 0.10,  # SSD persistent disk
                'database': {
                    'micro': 15,    # db-f1-micro
                    'small': 30,    # db-g1-small
                    'medium': 60,   # db-n1-standard-2
                    'large': 120    # db-n1-standard-4
                },
                'cache': {
                    'basic': 12,           # Basic 1GB
                    'standard': 25,        # Standard 2.5GB
                    'premium': 50,         # Standard 5GB
                    'premium-cluster': 100 # HA cluster
                },
                'networking': 20,  # Load Balancer
                'monitoring': 12,  # Cloud Monitoring
                'backup': 6       # Cloud Storage
            },
            'alicloud': {
                'compute': {
                    'small': 28,    # ecs.g6.large
                    'medium': 42,   # ecs.g6.xlarge
                    'large': 84,    # ecs.g6.2xlarge
                    'xlarge': 168   # ecs.g6.4xlarge
                },
                'storage_per_gb': 0.06,  # SSD Cloud Disk
                'database': {
                    'micro': 10,    # pg.n2.small.1
                    'small': 20,    # pg.n2.medium.1
                    'medium': 40,   # pg.n4.medium.1
                    'large': 80     # pg.n4.large.1
                },
                'cache': {
                    'basic': 8,            # Standard 256MB
                    'standard': 16,        # Standard 1GB
                    'premium': 32,         # Standard 2.5GB
                    'premium-cluster': 64  # Cluster mode
                },
                'networking': 15,  # SLB
                'monitoring': 8,   # CloudMonitor
                'backup': 4       # OSS backup
            }
        }
    
    def calculate_costs(self, provider: str, size: str) -> ResourceCosts:
        """Calculate total monthly costs for a provider and size"""
        pricing = self.pricing[provider]
        deployment = self.deployment_sizes[size]
        
        # Calculate each component
        compute_cost = pricing['compute'][deployment.node_type] * deployment.nodes
        storage_cost = pricing['storage_per_gb'] * deployment.storage_gb
        database_cost = pricing['database'][deployment.database_size]
        cache_cost = pricing['cache'][deployment.cache_size]
        
        # Fixed costs
        networking_cost = pricing['networking']
        monitoring_cost = pricing['monitoring']
        backup_cost = pricing['backup']
        
        return ResourceCosts(
            compute=compute_cost,
            storage=storage_cost,
            database=database_cost,
            cache=cache_cost,
            networking=networking_cost,
            monitoring=monitoring_cost,
            backup=backup_cost
        )
    
    def compare_all_providers(self, size: str) -> Dict[str, ResourceCosts]:
        """Compare costs across all providers for a given size"""
        return {
            provider: self.calculate_costs(provider, size)
            for provider in self.pricing.keys()
        }
    
    def generate_cost_report(self, size: str = 'medium') -> str:
        """Generate detailed cost comparison report"""
        deployment = self.deployment_sizes[size]
        comparison = self.compare_all_providers(size)
        
        report = f"""
=================================================================
          NEURON-AI MULTI-CLOUD COST COMPARISON
          Deployment Size: {deployment.name}
          Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
=================================================================

Deployment Configuration:
  - Nodes: {deployment.nodes}x {deployment.node_type}
  - Storage: {deployment.storage_gb}GB SSD
  - Database: {deployment.database_size}
  - Cache: {deployment.cache_size}

Monthly Cost Breakdown (USD):
"""
        
        # Sort providers by total cost
        sorted_providers = sorted(
            comparison.items(),
            key=lambda x: x[1].total
        )
        
        # Detailed breakdown
        for provider, costs in sorted_providers:
            savings = ""
            if provider != sorted_providers[0][0]:  # Not the cheapest
                cheapest_cost = sorted_providers[0][1].total
                diff = costs.total - cheapest_cost
                pct = (diff / cheapest_cost) * 100
                savings = f" (+${diff:.2f}, +{pct:.1f}%)"
            
            report += f"""
{provider.upper():>12}: ${costs.total:>7.2f}/month{savings}
  - Compute:    ${costs.compute:>6.2f} ({deployment.nodes}x {deployment.node_type})
  - Storage:    ${costs.storage:>6.2f} ({deployment.storage_gb}GB)
  - Database:   ${costs.database:>6.2f} ({deployment.database_size})
  - Cache:      ${costs.cache:>6.2f} ({deployment.cache_size})
  - Network:    ${costs.networking:>6.2f}
  - Monitor:    ${costs.monitoring:>6.2f}
  - Backup:     ${costs.backup:>6.2f}
"""
        
        # Summary and recommendations
        cheapest = sorted_providers[0]
        most_expensive = sorted_providers[-1]
        savings_potential = most_expensive[1].total - cheapest[1].total
        
        report += f"""
SUMMARY:
  Best Value: {cheapest[0].upper()} (${cheapest[1].total:.2f}/month)
  Max Savings: ${savings_potential:.2f}/month ({cheapest[0].upper()} vs {most_expensive[0].upper()})
  Annual TCO Range: ${cheapest[1].total*12:,.2f} - ${most_expensive[1].total*12:,.2f}

RECOMMENDATIONS:
  - Development: Use {cheapest[0].upper()} for cost efficiency
  - Production: Consider {sorted_providers[1][0].upper() if len(sorted_providers) > 1 else cheapest[0].upper()} for reliability balance
  - Multi-cloud: Start with {cheapest[0].upper()}, expand to others
"""
        
        return report
    
    def compare_sizes(self, provider: str) -> str:
        """Compare different deployment sizes for a single provider"""
        costs_by_size = {}
        for size in self.deployment_sizes.keys():
            costs_by_size[size] = self.calculate_costs(provider, size)
        
        report = f"""
{provider.upper()} DEPLOYMENT SIZE COMPARISON:
{'='*50}
"""
        
        for size, costs in costs_by_size.items():
            deployment = self.deployment_sizes[size]
            report += f"""
{deployment.name}:
  - Configuration: {deployment.nodes}x {deployment.node_type}, {deployment.storage_gb}GB
  - Monthly Cost: ${costs.total:.2f}
  - Annual Cost: ${costs.total*12:,.2f}
  - Cost per Node: ${costs.total/deployment.nodes:.2f}
"""
        
        return report
    
    def export_json(self, output_file: str):
        """Export cost data as JSON"""
        data = {
            'generated_at': datetime.now().isoformat(),
            'deployment_sizes': {k: asdict(v) for k, v in self.deployment_sizes.items()},
            'cost_comparison': {}
        }
        
        for size in self.deployment_sizes.keys():
            data['cost_comparison'][size] = {}
            for provider in self.pricing.keys():
                costs = self.calculate_costs(provider, size)
                data['cost_comparison'][size][provider] = asdict(costs)
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Cost data exported to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Multi-cloud cost calculator for Neuron-AI')
    parser.add_argument('--size', choices=['small', 'medium', 'large', 'enterprise'],
                      default='medium', help='Deployment size (default: medium)')
    parser.add_argument('--provider', choices=['aws', 'azure', 'gcp', 'alicloud'],
                      help='Compare sizes for specific provider')
    parser.add_argument('--export-json', help='Export data to JSON file')
    parser.add_argument('--all-sizes', action='store_true',
                      help='Show comparison for all sizes')
    
    args = parser.parse_args()
    
    calculator = MultiCloudCostCalculator()
    
    if args.export_json:
        calculator.export_json(args.export_json)
        return
    
    if args.provider:
        print(calculator.compare_sizes(args.provider))
        return
    
    if args.all_sizes:
        for size in ['small', 'medium', 'large', 'enterprise']:
            print(calculator.generate_cost_report(size))
            print("\n" + "="*70 + "\n")
        return
    
    # Default: show comparison for specified size
    print(calculator.generate_cost_report(args.size))
    
    # Quick deployment commands
    print("""
QUICK DEPLOYMENT COMMANDS:
  AWS:      ./deploy/quick-deploy.sh aws production
  Azure:    ./deploy/quick-deploy.sh azure production  
  GCP:      ./deploy/quick-deploy.sh gcp production
  AliCloud: ./deploy/quick-deploy.sh alicloud production

COST OPTIMIZATION TIPS:
  1. Use spot/preemptible instances for dev environments
  2. Enable auto-scaling to match demand
  3. Use reserved instances for production workloads
  4. Monitor and optimize data transfer costs
  5. Consider multi-cloud for better rates
""")

if __name__ == "__main__":
    main()