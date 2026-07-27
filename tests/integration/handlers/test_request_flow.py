import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.core.constants.enums import CancelledBy, DriverAvailability, RequestStatus
from bot.core.models.delivery_request import DeliveryRequest
from bot.request.service import RequestService
from bot.request.repository import RequestRepository
from bot.request.schemas import CreateRequestDTO
from bot.student.handler import (
    cancel_request_creation,
    process_pickup_detail,
    process_dropoff_address,
    process_hall_select,
    process_recipient_name,
    process_recipient_phone,
    process_luggage_size,
    process_luggage_count,
    process_preferred_date_callback,
    process_time_window_callback,
    skip_special_instructions,
    process_special_instructions,
    submit_request_creation,
    show_my_requests_list,
    start_request_edit,
    confirm_request_update,
    prompt_cancel_request,
    confirm_cancel_request,
)
from bot.student.states import RequestCreateFSM, RequestUpdateFSM
from datetime import date


def _make_message(text: str = "", user_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


def _make_callback(data: str = "", user_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = user_id
    cb.from_user.username = "testuser"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _make_state_with_data(data: dict) -> MagicMock:
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


class TestRequestCreationFlowIntegration:
    async def test_full_request_creation_flow(self):
        state = _make_state_with_data({})

        message = _make_message(text="Room 102", user_id=1)
        await process_pickup_detail(message, state)
        state.update_data.assert_awaited_with(pickup_detail="Room 102")
        state.set_state.assert_awaited_with(RequestCreateFSM.entering_dropoff_address)

    async def test_request_cancel_flow(self):
        event = _make_message(text="/cancel_request")
        state = AsyncMock()

        await cancel_request_creation(event, state)

        state.clear.assert_awaited_once()

    async def test_request_submit_with_service(self):
        callback = _make_callback(data="req_submit", user_id=1)
        state = _make_state_with_data({
            "pickup_detail": "Room 102",
            "dropoff_address": "123 Lagos St",
            "dropoff_landmark": None,
            "hall_of_residence": "Esther Hall",
            "recipient_name": "Jane",
            "recipient_phone": "08012345678",
            "luggage_size": "small",
            "luggage_count": "1",
            "preferred_date": "2025-08-15",
            "preferred_time_window": "8am-11am",
            "special_instructions": None,
        })
        state.clear = AsyncMock()

        session = AsyncMock()
        req = MagicMock(spec=DeliveryRequest)
        req.id = 1
        session.get.return_value = req

        repo = RequestRepository(session)
        repo.create = AsyncMock(return_value=req)

        service = RequestService(session)
        service.request_repo = repo

        await submit_request_creation(callback, state, session=session)

        state.clear.assert_awaited_once()

    async def test_my_requests_list_empty(self):
        message = _make_message(text="📋 My Requests", user_id=1)
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        await show_my_requests_list(message, session=session)

        message.answer.assert_awaited_once()


class TestRequestEditFlowIntegration:
    async def test_start_request_edit_blocks_non_pending(self):
        callback = _make_callback(data="my_req_edit:1", user_id=1)
        state = AsyncMock()

        req = MagicMock(spec=DeliveryRequest)
        req.id = 1
        req.student_id = 1
        req.status = RequestStatus.ASSIGNED

        session = AsyncMock()
        repo = RequestRepository(session)
        repo.get_by_id = AsyncMock(return_value=req)

        await start_request_edit(callback, state, session=session)

        callback.message.answer.assert_awaited_once()


class TestRequestCancelFlowIntegration:
    async def test_prompt_cancel_blocks_non_cancellable(self):
        callback = _make_callback(data="my_req_cancel:1", user_id=1)

        req = MagicMock(spec=DeliveryRequest)
        req.id = 1
        req.student_id = 1
        req.status = RequestStatus.DELIVERED

        session = AsyncMock()
        repo = RequestRepository(session)
        repo.get_by_id = AsyncMock(return_value=req)

        await prompt_cancel_request(callback, session=session)

        callback.message.answer.assert_awaited_once()

    async def test_confirm_cancel_restores_driver_availability(self):
        callback = _make_callback(data="my_req_cancel_confirm:1", user_id=1)
        state = AsyncMock()
        state.clear = AsyncMock()

        req = MagicMock(spec=DeliveryRequest)
        req.id = 1
        req.student_id = 1
        req.status = RequestStatus.ASSIGNED
        req.driver_id = 7

        session = AsyncMock()

        repo = RequestRepository(session)
        repo.get_by_id = AsyncMock(return_value=req)

        driver = MagicMock()
        driver.availability = DriverAvailability.BUSY
        session.get = AsyncMock(side_effect=lambda model, id: driver if model.__name__ == "DriverProfile" else req)

        service = RequestService(session)
        service.request_repo = repo

        updated_req = MagicMock()
        updated_req.id = 1
        updated_req.driver_id = 7
        service.cancel_request = AsyncMock(return_value=(updated_req, MagicMock()))

        await confirm_cancel_request(callback, session=session)

        assert driver.availability == DriverAvailability.AVAILABLE
        assert session.flush.call_count >= 1
