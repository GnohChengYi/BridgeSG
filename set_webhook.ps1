# Replace $Token with actual bot token
# Copy entire code and paste in terminal

$Token = "<YOUR_BOT_TOKEN>"
$WebhookUrl = "https://bridge-sg.vercel.app/telegram"

# Construct the URI with properly escaped allowed_updates JSON array
$Uri = "https://api.telegram.org/bot$Token/setWebhook?url=$WebhookUrl&allowed_updates=[`"message`",`"channel_post`"]"

# Make the request to Telegram
Invoke-RestMethod -Uri $Uri -Method Get