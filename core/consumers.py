from channels.generic.websocket import AsyncWebsocketConsumer
import json

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get user from scope (set by auth middleware)
        self.user = self.scope.get('user')
        
        if not self.user.is_authenticated:
            await self.close()
            return
            
        # Join user-specific group
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Send connection confirmation
        await self.send(json.dumps({
            "type": "connection_established",
            "message": "Connected to notifications"
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Handle incoming messages (e.g., mark as read)
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'mark_read':
            # Handle marking notification as read
            pass

    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send(json.dumps({
            "type": "notification",
            "notification": event['notification']
        }))