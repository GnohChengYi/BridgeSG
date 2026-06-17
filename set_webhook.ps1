# PowerShell -ExecutionPolicy Bypass -File .\set_webhook.ps1

$Token = ""
$WebhookUrl = "https://bridge-sg.vercel.app/telegram"

$AllowedUpdates = '["message","channel_post","callback_query","inline_query"]'

$BaseUrl = "https://api.telegram.org/bot{0}/setWebhook" -f $Token
$Uri = "{0}?url={1}&allowed_updates={2}" -f $BaseUrl, $WebhookUrl, $AllowedUpdates

# Make the request to Telegram
Invoke-RestMethod -Uri $Uri -Method Get