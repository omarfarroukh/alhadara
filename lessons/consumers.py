import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from courses.models import ScheduleSlot
from .models import ScheduleSlotNews
from .serializers import ScheduleSlotNewsSerializer

class NewsFeedConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slot_id = self.scope["url_route"]["kwargs"]["slot_id"]
        self.user = self.scope["user"]
        self.group_name = f"slot_news_{self.slot_id}"

        if not self.user.is_authenticated:
            await self.close()
            return

        # Authorise access
        try:
            await self.check_permission()
        except PermissionDenied:
            await self.close()
            return

        # Join slot-specific group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial list
        await self.push_news_list()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """
        Expected JSON:
        {"type": "post",  ...fields same as DRF view...}
        {"type": "mark_read", "id": <news_pk>}
        """
        try:
            data = json.loads(text_data)
        except ValueError:
            return

        msg_type = data.get("type")

        if msg_type == "post":
            await self.handle_post(data)
        elif msg_type == "mark_read":
            await self.handle_mark_read(data.get("id"))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    async def news_item_posted(self, event):
        """Broadcast when a new item is created"""
        await self.send(text_data=json.dumps({
            "type": "new_item",
            "notification": event["payload"]
        }))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @database_sync_to_async
    def check_permission(self):
        slot = get_object_or_404(
            ScheduleSlot.objects.select_related("teacher"),
            id=self.slot_id
        )
        user = self.user
        if not (user == slot.teacher or slot.enrollments.filter(student=user).exists()):
            raise PermissionDenied

    async def push_news_list(self):
        payload = await self.get_news_list()
        await self.send(text_data=json.dumps({
            "type": "initial_list",
            "notifications": payload
        }))

    @database_sync_to_async
    def get_news_list(self):
        qs = (
            ScheduleSlotNews.objects
            .filter(schedule_slot_id=self.slot_id)
            .select_related(
                "author",
                "file_storage",
                "related_homework",
                "related_quiz"
            )
            .order_by("-created_at")
        )
        return ScheduleSlotNewsSerializer(qs, many=True, context={"request": None}).data

    async def handle_post(self, data):
        """
        Create a new ScheduleSlotNews item (teacher only) and broadcast.
        """
        try:
            instance = await self.create_news_item(data)
        except PermissionDenied:
            await self.send(json.dumps({"type": "error", "detail": "Not allowed"}))
            return

        payload = await self.serialize_single(instance)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "news_item_posted", "payload": payload}
        )

    @database_sync_to_async
    def create_news_item(self, data):
        slot = get_object_or_404(ScheduleSlot, id=self.slot_id)
        if not (self.user.user_type == "teacher" and self.user == slot.teacher):
            raise PermissionDenied

        serializer = ScheduleSlotNewsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(author=self.user, schedule_slot=slot)

    async def handle_mark_read(self, news_pk):
        # implement your read-receipt logic here
        pass

    @database_sync_to_async
    def serialize_single(self, instance):
        return ScheduleSlotNewsSerializer(instance, context={"request": None}).data