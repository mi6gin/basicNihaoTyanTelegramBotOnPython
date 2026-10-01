from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from nihao_tyan.telegram.callbacks import Callback
from nihao_tyan.telegram.constants import CATEGORIES, QUICK_REPLY_KEYS
from nihao_tyan.i18n import translate


def admin_menu_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("admin.pending_appeals", language), callback_data=Callback("adminlist", user_id, "pending.0").pack())],
            [InlineKeyboardButton(text=translate("admin.all_appeals", language), callback_data=Callback("adminlist", user_id, "all.0").pack())],
            [InlineKeyboardButton(text=translate("admin.categories", language), callback_data=Callback("admincats", user_id).pack())],
            [InlineKeyboardButton(text=translate("admin.logs", language), callback_data=Callback("adminlogs", user_id, "0").pack())],
            [InlineKeyboardButton(text=translate("admin.users", language), callback_data=Callback("adminusers", user_id, "0").pack())],
            [InlineKeyboardButton(text=translate("admin.chats", language), callback_data=Callback("admingroups", user_id, "0").pack())],
            [InlineKeyboardButton(text=translate("broadcast.menu_button", language), callback_data=Callback("broadcast", user_id).pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("main", user_id).pack())],
        ]
    )


def broadcast_menu_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("broadcast.news", language), callback_data=Callback("broadcastnews", user_id).pack())],
            [InlineKeyboardButton(text=translate("broadcast.ad", language), callback_data=Callback("broadcastad", user_id).pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("admin", user_id).pack())],
        ]
    )


def broadcast_audience_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("broadcast.audience_all", language), callback_data=Callback("broadcastto", user_id, "all").pack())],
            [InlineKeyboardButton(text=translate("broadcast.audience_admins", language), callback_data=Callback("broadcastto", user_id, "admins").pack())],
            [InlineKeyboardButton(text=translate("broadcast.audience_selected", language), callback_data=Callback("broadcastto", user_id, "selected").pack())],
            [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("broadcastcancel", user_id).pack())],
        ]
    )


def broadcast_users_keyboard(
    user_id: int,
    language: str,
    users: list[tuple[int, str | None, str, str | None]],
    selected_ids: set[int],
    page: int,
    count: int,
    page_size: int = 8,
    search_active: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []
    for telegram_id, username, first_name, last_name in users:
        display_name = f"@{username}" if username else " ".join(filter(None, (first_name, last_name)))
        display_name = display_name[:28] or str(telegram_id)
        marker = "✅" if telegram_id in selected_ids else "▫️"
        buttons.append(
            [InlineKeyboardButton(text=f"{marker} {display_name} · {telegram_id}", callback_data=Callback("broadcastpick", user_id, str(telegram_id)).pack())]
        )
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(
            text=translate("button.newer", language), callback_data=Callback("broadcastpage", user_id, str(page - 1)).pack(),
        ))
    if (page + 1) * page_size < count:
        navigation.append(InlineKeyboardButton(
            text=translate("button.older", language), callback_data=Callback("broadcastpage", user_id, str(page + 1)).pack(),
        ))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text=translate("broadcast.search", language), callback_data=Callback("broadcastsearch", user_id).pack())])
    if search_active:
        buttons.append([InlineKeyboardButton(text=translate("broadcast.clear_search", language), callback_data=Callback("broadcastclear", user_id).pack())])
    buttons.append([InlineKeyboardButton(text=translate("broadcast.users_ready", language), callback_data=Callback("broadcastready", user_id).pack())])
    buttons.append([InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("broadcastcancel", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_search_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("broadcastsearchback", user_id).pack())],
        [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("broadcastcancel", user_id).pack())],
    ])


def broadcast_cancel_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("broadcastcancel", user_id).pack())]
        ]
    )


def broadcast_confirm_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("broadcast.send", language), callback_data=Callback("broadcastsend", user_id).pack())],
            [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("broadcastcancel", user_id).pack())],
        ]
    )


def broadcast_ad_keyboard(button_text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=url)]])


def admin_logs_keyboard(user_id: int, language: str, dates: list[str], offset: int, page_size: int = 7) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=day, callback_data=Callback("adminlog", user_id, day).pack())] for day in dates[offset : offset + page_size]]
    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton(text=translate("button.newer", language), callback_data=Callback("adminlogs", user_id, str(max(0, offset - page_size))).pack())
        )
    if offset + page_size < len(dates):
        navigation.append(
            InlineKeyboardButton(text=translate("button.older", language), callback_data=Callback("adminlogs", user_id, str(offset + page_size)).pack())
        )
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("admin", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_log_summary_keyboard(user_id: int, language: str, day: str, has_file: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_file:
        buttons.extend(
            [
                [InlineKeyboardButton(text=translate("admin.view_records", language), callback_data=Callback("adminlogentry", user_id, f"{day}.0").pack())],
                [InlineKeyboardButton(text=translate("admin.download_log", language), callback_data=Callback("adminlogfile", user_id, day).pack())],
            ]
        )
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("adminlogs", user_id, "0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_log_entry_keyboard(user_id: int, language: str, day: str, offset: int, count: int) -> InlineKeyboardMarkup:
    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton(text=translate("button.newer", language), callback_data=Callback("adminlogentry", user_id, f"{day}.{offset - 1}").pack())
        )
    if offset + 1 < count:
        navigation.append(
            InlineKeyboardButton(text=translate("button.older", language), callback_data=Callback("adminlogentry", user_id, f"{day}.{offset + 1}").pack())
        )
    buttons = [navigation] if navigation else []
    buttons.extend(
        [
            [InlineKeyboardButton(text=translate("admin.download_log", language), callback_data=Callback("adminlogfile", user_id, day).pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("adminlog", user_id, day).pack())],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_directory_keyboard(user_id: int, language: str, action: str, offset: int, count: int) -> InlineKeyboardMarkup:
    navigation = []
    if offset > 0:
        navigation.append(InlineKeyboardButton(text=translate("button.newer", language), callback_data=Callback(action, user_id, str(offset - 1)).pack()))
    if offset + 1 < count:
        navigation.append(InlineKeyboardButton(text=translate("button.older", language), callback_data=Callback(action, user_id, str(offset + 1)).pack()))
    buttons = [navigation] if navigation else []
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("admin", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_categories_keyboard(user_id: int, language: str, counts: dict[str, int]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{translate(f'category.{category}', language)} · {counts.get(category, 0)}",
                callback_data=Callback("adminlist", user_id, f"{category}.0").pack(),
            )
        ]
        for category in CATEGORIES
    ]
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("admin", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_empty_category_keyboard(user_id: int, language: str, filter_name: str) -> InlineKeyboardMarkup:
    category = filter_name[:-4] if filter_name.endswith("_all") else filter_name
    target = category if filter_name.endswith("_all") else f"{category}_all"
    label = "admin.only_open" if filter_name.endswith("_all") else "admin.show_all_in_category"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate(label, language), callback_data=Callback("adminlist", user_id, f"{target}.0").pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("admincats", user_id).pack())],
        ]
    )


def admin_appeals_keyboard(
    user_id: int,
    language: str,
    offset: int,
    count: int,
    appeal_id: int,
    filter_name: str,
) -> InlineKeyboardMarkup:
    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton(
                text=translate("button.newer", language),
                callback_data=Callback("adminlist", user_id, f"{filter_name}.{offset - 1}").pack(),
            )
        )
    if offset + 1 < count:
        navigation.append(
            InlineKeyboardButton(
                text=translate("button.older", language),
                callback_data=Callback("adminlist", user_id, f"{filter_name}.{offset + 1}").pack(),
            )
        )
    buttons = [navigation] if navigation else []
    buttons.extend(
        [
            [
                InlineKeyboardButton(
                    text=translate("button.view", language),
                    callback_data=Callback("adminappeal", user_id, f"{appeal_id}.{filter_name}.{offset}").pack(),
                )
            ],
        ]
    )
    category = filter_name[:-4] if filter_name.endswith("_all") else filter_name
    if category in CATEGORIES:
        target = category if filter_name.endswith("_all") else f"{category}_all"
        label = "admin.only_open" if filter_name.endswith("_all") else "admin.show_all_in_category"
        buttons.append([InlineKeyboardButton(text=translate(label, language), callback_data=Callback("adminlist", user_id, f"{target}.0").pack())])
    back_action = "admincats" if category in CATEGORIES else "admin"
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback(back_action, user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_appeal_keyboard(
    user_id: int,
    language: str,
    appeal_id: int,
    filter_name: str,
    offset: int,
    can_answer: bool,
    has_attachments: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []
    if has_attachments:
        buttons.append(
            [InlineKeyboardButton(text=translate("support.attachments", language), callback_data=Callback("adminfiles", user_id, str(appeal_id)).pack())]
        )
    if can_answer:
        buttons.extend(
            [
                [
                    InlineKeyboardButton(
                        text=translate("admin.reply", language),
                        callback_data=Callback("adminreply", user_id, str(appeal_id)).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=translate("admin.close", language),
                        callback_data=Callback("adminclose", user_id, str(appeal_id)).pack(),
                    )
                ],
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=translate("button.back", language),
                callback_data=Callback("adminlist", user_id, f"{filter_name}.{offset}").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_cancel_keyboard(user_id: int, language: str, appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("button.cancel", language),
                    callback_data=Callback("admincancel", user_id, str(appeal_id)).pack(),
                )
            ],
        ]
    )


def admin_reply_templates_keyboard(user_id: int, language: str, appeal_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=translate(f"admin.quick_label_{key}", language),
            callback_data=Callback("adminquick", user_id, f"{appeal_id}.{key}").pack(),
        )]
        for key in QUICK_REPLY_KEYS
    ]
    buttons.append([InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("admincancel", user_id, str(appeal_id)).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_quick_preview_keyboard(user_id: int, language: str, appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("admin.quick_send", language), callback_data=Callback("adminquicksend", user_id, str(appeal_id)).pack())],
        [InlineKeyboardButton(text=translate("admin.quick_edit", language), callback_data=Callback("adminquickedit", user_id, str(appeal_id)).pack())],
        [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("admincancel", user_id, str(appeal_id)).pack())],
    ])


def admin_notice_keyboard(admin_id: int, appeal_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("button.view", language),
                    callback_data=Callback("adminappeal", admin_id, f"{appeal_id}.pending.0").pack(),
                )
            ]
        ]
    )
