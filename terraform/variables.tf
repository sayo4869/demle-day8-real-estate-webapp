# ここにある値を terraform.tfvars で変えるだけで、別の環境に同じ構成を作れる

variable "owner" {
  description = "自分の名前（英数字）。リソース名に付くので、同じアカウントで複数人が使ってもぶつからない"
  type        = string
}

variable "aws_profile" {
  description = "aws configure --profile で登録したプロファイル名。null なら default（または環境変数 AWS_PROFILE）を使う"
  type        = string
  default     = null
}

variable "region" {
  description = "AWS のリージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "instance_type" {
  description = "EC2 のインスタンスタイプ（Day7 と同じ t2.micro。使えないアカウントでは t3.micro）"
  type        = string
  default     = "t2.micro"
}

variable "public_key_path" {
  description = "SSH の公開鍵のパス（ssh-keygen で作ったもの）。秘密鍵は Terraform に渡さない"
  type        = string
  default     = "~/.ssh/demle_day8.pub"
}

variable "private_key_path" {
  description = "SSH の秘密鍵のパス。モデルを EC2 に送るとき（scp の代わり）にだけ使う。AWS には送られない"
  type        = string
  default     = "~/.ssh/demle_day8"
}

variable "allowed_cidr" {
  description = "SSH(22) と Web アプリ(8080) に接続してよい IP の範囲。自分の IP なら \"203.0.113.10/32\" のように書く"
  type        = string
  default     = "0.0.0.0/0" # Day7 と同じ「どこからでも」。本番では自分の IP に絞る
}

variable "repo_url" {
  description = "EC2 で clone するコード"
  type        = string
  default     = "https://github.com/sayo4869/demle-day8-real-estate-webapp.git"
}

variable "repo_branch" {
  description = "clone するブランチ"
  type        = string
  default     = "main"
}

variable "model_dir" {
  description = "model.pickle と scaler.pickle があるフォルダ（手元の PC）"
  type        = string
  default     = ".."
}
