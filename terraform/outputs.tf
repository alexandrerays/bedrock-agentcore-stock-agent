# Output values for deployment

output "deployment_summary" {
  description = "Summary of deployed Agentcore resources"
  value = {
    region               = var.aws_region
    environment          = var.environment
    cognito_user_pool_id = aws_cognito_user_pool.stock_agent.id
    cognito_client_id    = aws_cognito_user_pool_client.stock_agent_client.id
    cognito_region       = var.aws_region
    documents_bucket     = aws_s3_bucket.documents.id
    docker_image_uri     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.app_name}:latest"
  }
}

output "authentication" {
  description = "Authentication configuration"
  value = {
    user_pool_id  = aws_cognito_user_pool.stock_agent.id
    client_id     = aws_cognito_user_pool_client.stock_agent_client.id
    region        = var.aws_region
    test_username = var.cognito_username
  }
  sensitive = false
}

output "resources" {
  description = "Created AWS resources for Agentcore"
  value = {
    agent_role_arn   = aws_iam_role.agent_role.arn
    documents_bucket = aws_s3_bucket.documents.id
  }
}
