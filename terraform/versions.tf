# Terraform 本体と、使うプロバイダ（AWS を操作するためのプラグイン）のバージョン
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = var.region      # Day7 と同じ東京リージョン（ap-northeast-1）
  profile = var.aws_profile # どの AWS アカウントのアクセスキーを使うか

  # この Terraform で作ったものに共通のタグを付ける（AWS 画面で見分けやすくなる）
  default_tags {
    tags = {
      Project   = "demle-day8"
      Owner     = var.owner
      ManagedBy = "terraform"
    }
  }
}
