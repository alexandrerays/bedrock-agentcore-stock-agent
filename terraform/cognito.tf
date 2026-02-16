# Cognito User Pool for authentication

# Cognito User Pool
resource "aws_cognito_user_pool" "stock_agent" {
  name = "${var.app_name}-user-pool"

  password_policy {
    minimum_length    = 8
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  username_attributes = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration = "OFF"

  tags = var.tags
}

# Cognito User Pool Client
resource "aws_cognito_user_pool_client" "stock_agent_client" {
  name                = "${var.app_name}-client"
  user_pool_id        = aws_cognito_user_pool.stock_agent.id
  generate_secret     = false
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  read_attributes = [
    "email",
    "name",
    "given_name",
    "family_name"
  ]

  write_attributes = [
    "email",
    "name",
    "given_name",
    "family_name"
  ]
}

# Test User
resource "aws_cognito_user" "test_user" {
  user_pool_id = aws_cognito_user_pool.stock_agent.id
  username     = "${var.cognito_username}@example.com"
  password     = var.cognito_password

  attributes = {
    email          = "${var.cognito_username}@example.com"
    name           = "Evaluator User"
    email_verified = "true"
  }

  message_action = "SUPPRESS"

  depends_on = [aws_cognito_user_pool.stock_agent]
}

# Temporary password will be handled by message_action = SUPPRESS above
# Users can set their own password on first login or via admin API

# Outputs for Cognito
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.stock_agent.id
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.stock_agent.arn
}

output "cognito_client_id" {
  description = "Cognito Client ID"
  value       = aws_cognito_user_pool_client.stock_agent_client.id
}

output "cognito_region" {
  description = "AWS Region for Cognito"
  value       = var.aws_region
}

output "cognito_test_username" {
  description = "Test user username"
  value       = var.cognito_username
}

output "cognito_test_user_pool_domain" {
  description = "Cognito User Pool domain"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.stock_agent.id}"
}

