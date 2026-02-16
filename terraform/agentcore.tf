# Docker image URI for Agentcore deployment (configured via Agentcore console)

output "docker_image_uri" {
  description = "Docker image URI in ECR for Agentcore deployment"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.app_name}:latest"
}
