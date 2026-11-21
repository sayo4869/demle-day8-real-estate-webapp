# Day7・Day8 で AWS の画面とターミナルで手作業していたことを、コードで書いたもの
#
#   手作業                                   Terraform
#   ─────────────────────────────────────  ─────────────────────────────
#   Amazon Linux 2023 を選ぶ               data "aws_ssm_parameter" "al2023"
#   キーペアを作る                          aws_key_pair.this
#   セキュリティグループで 22・8080 を開ける aws_security_group.web
#   インスタンスを起動する                  aws_instance.web
#   git・pip を入れて clone、pip install   user_data.sh.tftpl（起動時に自動で実行）
#   uvicorn を起動（SSH を閉じても動かす）  user_data.sh.tftpl の systemd 設定
#   scp でモデルを送る                      terraform_data.model

# ---------- OS（AMI）：Amazon Linux 2023 の最新版 ----------
# AMI の ID はリージョンや時期で変わるので、AWS が公開している「最新版の ID」を調べて使う
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# ---------- ネットワーク：アカウントに最初からある VPC を使う（画面の「変更なし」と同じ） ----------
data "aws_vpc" "default" {
  default = true
}

# ---------- キーペア：手元で作った公開鍵を AWS に登録する ----------
resource "aws_key_pair" "this" {
  key_name   = "demle-day8-${var.owner}"
  public_key = file(pathexpand(var.public_key_path))
}

# ---------- セキュリティグループ：EC2 の入口 ----------
resource "aws_security_group" "web" {
  name        = "demle-day8-${var.owner}"
  description = "SSH and FastAPI (8080) for Day8 web app"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.web.id
  description       = "SSH"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.allowed_cidr
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  security_group_id = aws_security_group.web.id
  description       = "FastAPI (uvicorn)"
  ip_protocol       = "tcp"
  from_port         = 8080
  to_port           = 8080
  cidr_ipv4         = var.allowed_cidr
}

# 出口はすべて許可（yum や git clone、pip install のため。画面で作ったときと同じ）
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.web.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# ---------- EC2 インスタンス ----------
resource "aws_instance" "web" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.this.key_name
  vpc_security_group_ids      = [aws_security_group.web.id]
  associate_public_ip_address = true

  # 起動したときに1回だけ実行されるスクリプト（Day8 の 13章①と、Day7 の systemd の手順）
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url    = var.repo_url
    repo_branch = var.repo_branch
  })
  user_data_replace_on_change = true # スクリプトを変えたら、インスタンスを作り直す

  root_block_device {
    volume_size = 8 # GiB（画面の初期値と同じ）
    volume_type = "gp3"
    encrypted   = true
  }

  # インスタンスの情報を取るとき、トークンを必須にする（IMDSv2。今の AWS のおすすめ設定）
  metadata_options {
    http_tokens = "required"
  }

  tags = {
    Name = "demle-day8-${var.owner}"
  }
}

# ---------- モデルを EC2 に送る（Day8 の 13章② scp の代わり） ----------
# モデルは GitHub に置かない（11章）ので、手元の PC から直接送る。
# モデルを作り直したら、terraform apply をもう一度実行すると送り直してアプリを再起動する。
resource "terraform_data" "model" {
  triggers_replace = [
    aws_instance.web.id,
    filesha256("${var.model_dir}/model.pickle"),
    filesha256("${var.model_dir}/scaler.pickle"),
  ]

  connection {
    type        = "ssh"
    host        = aws_instance.web.public_ip
    user        = "ec2-user"
    private_key = file(pathexpand(var.private_key_path))
  }

  # 起動スクリプト（clone と pip install）が終わるまで待つ
  provisioner "remote-exec" {
    inline = ["cloud-init status --wait > /dev/null || true", "test -d /home/ec2-user/webapp"]
  }

  provisioner "file" {
    source      = "${var.model_dir}/model.pickle"
    destination = "/home/ec2-user/webapp/model.pickle"
  }

  provisioner "file" {
    source      = "${var.model_dir}/scaler.pickle"
    destination = "/home/ec2-user/webapp/scaler.pickle"
  }

  provisioner "remote-exec" {
    inline = ["sudo systemctl restart webapp"]
  }
}
