terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state management
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "stock-agent/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
  profile = "assessment"

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "bedrock-stock-agent"
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  app_name = "bedrock-stock-agent"
  tags = {
    Name        = local.app_name
    Environment = var.environment
  }
}
