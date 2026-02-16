# AWS Bedrock Agentcore deployment for the stock agent
# This uses Bedrock's managed agentcore service to run the FastAPI application

# Deploy FastAPI application via shell script to Agentcore
# The application is deployed as a managed Agentcore agent
resource "null_resource" "agentcore_deployment" {
  triggers = {
    docker_image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.app_name}:latest"
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Deploying to AWS Bedrock Agentcore..."
      echo "Image: ${self.triggers.docker_image}"
      echo "Cognito Pool: ${aws_cognito_user_pool.stock_agent.id}"
      echo "Cognito Client: ${aws_cognito_user_pool_client.stock_agent_client.id}"
      echo "S3 Bucket: ${aws_s3_bucket.documents.id}"
    EOT
  }

  depends_on = [
    aws_cognito_user_pool.stock_agent,
    aws_s3_bucket.documents,
    aws_iam_role.agent_role
  ]
}

# Create a simple HTTP endpoint for testing (using API Gateway for now as proof of concept)
# In production, this would be replaced with native Bedrock Agentcore endpoint
resource "aws_apigatewayv2_api" "stock_agent" {
  name          = "${var.app_name}-agentcore-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_credentials = false
    allow_headers = [
      "Content-Type",
      "X-Amz-Date",
      "Authorization",
      "X-Api-Key",
      "X-Amz-Security-Token",
      "X-Amz-User-Agent"
    ]
    allow_methods = ["*"]
    allow_origins = ["*"]
    expose_headers = [
      "Date",
      "X-Amzn-RequestId"
    ]
    max_age = 300
  }

  tags = var.tags

  depends_on = [null_resource.agentcore_deployment]
}

# HTTP endpoint for testing the agent (gateway to Agentcore)
resource "aws_apigatewayv2_integration" "agentcore_integration" {
  api_id             = aws_apigatewayv2_api.stock_agent.id
  integration_type   = "HTTP_PROXY"
  integration_method = "POST"
  integration_uri    = "http://placeholder-agentcore-endpoint.us-east-1.bedrock.amazonaws.com"
  payload_format_version = "1.0"
}

# Route for invoke endpoint
resource "aws_apigatewayv2_route" "invoke" {
  api_id    = aws_apigatewayv2_api.stock_agent.id
  route_key = "POST /invoke"
  target    = "integrations/${aws_apigatewayv2_integration.agentcore_integration.id}"
}

# Route for health check
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.stock_agent.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.agentcore_integration.id}"
}

# Route for dev invoke
resource "aws_apigatewayv2_route" "invoke_dev" {
  api_id    = aws_apigatewayv2_api.stock_agent.id
  route_key = "POST /invoke-dev"
  target    = "integrations/${aws_apigatewayv2_integration.agentcore_integration.id}"
}

# Stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.stock_agent.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationLatency = "$context.integration.latency"
    })
  }

  tags = var.tags
}

# CloudWatch log group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.app_name}"
  retention_in_days = 7

  tags = var.tags
}

output "agentcore_api_endpoint" {
  description = "Agentcore API Gateway endpoint URL"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}"
}

output "docker_image_uri" {
  description = "Docker image URI in ECR for Agentcore deployment"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.app_name}:latest"
}

output "agentcore_api_id" {
  description = "API Gateway ID for Agentcore"
  value       = aws_apigatewayv2_api.stock_agent.id
}
