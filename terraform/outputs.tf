# terraform apply の最後に表示される値

output "app_url" {
  description = "ブラウザで開く URL"
  value       = "http://${aws_instance.web.public_dns}:8080/"
}

output "ssh_command" {
  description = "EC2 にログインするコマンド"
  value       = "ssh -i ${var.private_key_path} ec2-user@${aws_instance.web.public_dns}"
}

output "instance_id" {
  value = aws_instance.web.id
}
