from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
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
        
    async def notification_counter(self, event):
        # Nothing to do here – CounterConsumer already handles it
        pass
        
class CounterConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # initial value
        await self._send_counter(user)

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    # handler triggered by the same signal that feeds the full consumer
    async def notification_counter(self, event):
        await self.send(text_data=json.dumps({
            "type": "counter",
            "unread_count": event["unread_count"]
        }))

    async def notification_message(self, event):
        """
        Counter consumer does not need full notification objects;
        silently drop them to avoid the 'no handler' exception.
        """
        pass
    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def _send_counter(self, user):
        count = await self._get_unread_count(user)
        await self.send(text_data=json.dumps({
            "type": "counter",
            "unread_count": count
        }))

    @database_sync_to_async
    def _get_unread_count(self, user):
        return user.notifications.filter(is_read=False).count()