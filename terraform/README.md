# Terraform で Day8 のインフラを作る

Day7・Day8 で AWS の画面とターミナルで手作業していたことを、コード（Terraform）にしたものです。
`terraform apply` を1回実行すると、次のことがすべて自動で行われます。

| 手作業（Day7・Day8） | Terraform |
|---|---|
| Amazon Linux 2023 を選ぶ | `data.aws_ssm_parameter.al2023` |
| キーペアを作る | `aws_key_pair.this` |
| セキュリティグループで 22・8080 を開ける | `aws_security_group.web` とルール |
| インスタンスを起動する | `aws_instance.web` |
| git・pip を入れて clone、pip install | `user_data.sh.tftpl`（起動時に自動実行） |
| uvicorn を起動して、SSH を閉じても動かす | `user_data.sh.tftpl` の systemd 設定 |
| scp でモデルを送る | `terraform_data.model` |

`terraform.tfvars` の値を変えるだけで、別の人・別のリージョン・別のアカウントにも同じ構成を作れます。

## 0. 道具を入れる（初回のみ）

### Mac（Homebrew）

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
brew install awscli
```

### Windows（PowerShell）

```powershell
winget install --id Hashicorp.Terraform -e
winget install --id Amazon.AWSCLI -e
```

入れたあとはターミナルを開き直して、バージョンが出れば OK です。

```bash
terraform -version
aws --version
```

## 1. AWS のアクセスキーを用意して登録する

Terraform は、AWS の画面にログインする代わりに **アクセスキー**（AWS を操作するための鍵）を使います。
AWS の画面右上の自分の名前 →「セキュリティ認証情報」→「アクセスキーを作成」で作り、「.csv ファイルをダウンロード」を押します（講師から配られる場合はそれを使う）。
ダウンロードした `ユーザー名_accessKeys.csv` を開き、中のアクセスキー ID とシークレットアクセスキーを `aws configure` に貼り付けます。

```bash
aws configure
# AWS Access Key ID     : （CSV の Access key ID を貼る）
# AWS Secret Access Key : （CSV の Secret access key を貼る）
# Default region name   : ap-northeast-1
# Default output format : json

# 登録できたか確認（自分のアカウント ID が表示されれば OK）
aws sts get-caller-identity
```

> アクセスキーは GitHub のトークンと同じく、**絶対に GitHub に push しない**。登録したら CSV はダウンロードフォルダに置きっぱなしにしない。使い終わったら AWS の画面で無効化・削除する。

## 2. SSH の鍵を作る（初回のみ）

パスフレーズを聞かれたら、何も入れずに Enter を2回押します。

```bash
# Mac / Git Bash
ssh-keygen -t ed25519 -f ~/.ssh/demle_day8
```

```powershell
# PowerShell
ssh-keygen -t ed25519 -f "$HOME\.ssh\demle_day8"
```

AWS に登録されるのは公開鍵（`demle_day8.pub`）だけです。秘密鍵（`demle_day8`）は自分の PC から出ません。

## 3. 設定ファイルを作る

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars    # PowerShell は copy
```

`terraform.tfvars` の `owner` を自分の名前（英数字）に書き換えます。

モデル（`model.pickle` と `scaler.pickle`）は、この `terraform` フォルダの1つ上（`webapp` フォルダ）に置いておきます（Day8 10章②と同じ場所）。

## 4. 作る

```bash
terraform init     # 初回のみ。AWS 用のプラグインをダウンロード
terraform plan     # 何が作られるかを確認するだけ（まだ何も作らない）
terraform apply    # 本当に作る。yes と入力
```

数分待つと、最後に URL が表示されます。

```
app_url     = "http://ec2-XX-XX-XX-XX.ap-northeast-1.compute.amazonaws.com:8080/"
ssh_command = "ssh -i ~/.ssh/demle_day8 ec2-user@ec2-XX-XX-XX-XX.ap-northeast-1.compute.amazonaws.com"
```

モデルを作り直したときは、もう一度 `terraform apply` を実行すると、モデルを送り直してアプリを再起動します。

## 5. 片付ける

```bash
terraform destroy  # 作ったものを全部消す。yes と入力
```

EC2 は動かしている間お金がかかります。使い終わったら必ず destroy します。

## 注意

- `terraform.tfstate`（作ったものの記録）、`terraform.tfvars`、`.terraform/` は `.gitignore` に入っているので push されません。
- 0.0.0.0/0 は世界中から接続できる設定です。`allowed_cidr` を自分の IP（例：`203.0.113.10/32`）にするのがおすすめです。
- うまく動かないときは、`ssh_command` でログインして `sudo cat /var/log/cloud-init-output.log`（起動スクリプトのログ）や `sudo journalctl -u webapp`（アプリのログ）を見ます。
