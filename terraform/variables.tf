variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "cognito_username" {
  description = "Cognito test user username"
  type        = string
}

variable "cognito_password" {
  description = "Cognito test user password"
  type        = string
  sensitive   = true
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "bedrock-stock-agent"
}


variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "bedrock-stock-agent"
    Environment = "dev"
  }
}
