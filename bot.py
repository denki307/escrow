import os
import asyncio
import random
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import pyromod

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

app = Client("escrow_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

ADMINS = [OWNER_ID] if OWNER_ID else []
COMMISSION_PERCENT = 5
deals_db = {}

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    if message.chat.type.value == "private":
        instructions = (
            "**Welcome to Secure Escrow Service!** 🛡️\n\n"
            "Click the button below to start a new deal directly via interactive prompt."
        )
        buttons = [[InlineKeyboardButton("🟢 Start New Deal (DM)", callback_data="dm_start_deal")]]
        await message.reply_text(instructions, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        instructions = (
            "**Welcome to Secure Escrow Service!** 🛡️\n\n"
            "**How to Use:**\n"
            "1. Type `/format` to see the correct deal layout.\n"
            "2. Admins reply with `/newdeal` in groups or use DM start."
        )
        buttons = []
        for admin_id in ADMINS:
            try:
                user = await client.get_users(admin_id)
                name = user.first_name
            except:
                name = str(admin_id)
            buttons.append([InlineKeyboardButton(f"✅ Verified Admin: {name}", url=f"tg://user?id={admin_id}")])
        await message.reply_text(instructions, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("format"))
async def format_cmd(client: Client, message: Message):
    format_text = (
        "**📋 Escrow Deal Submission Format:**\n\n"
        "Buyer: @buyer_username\n"
        "Seller: @seller_username\n"
        "Item: Music Bot Code\n"
        "Amount: 500\n"
        "Time: 30\n"
        "Admin username: @admin_username"
    )
    await message.reply_text(format_text)

@app.on_message(filters.command("check"))
async def check_ticket(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ Usage: `/check <ticket_id>`")
        return

    ticket_id = message.command[1].strip()
    deal = deals_db.get(ticket_id)

    if not deal:
        await message.reply_text(f"❌ No deal found with Ticket ID: `{ticket_id}`.")
        return

    status_text = (
        f"🔍 **DEAL STATUS REPORT** (Ticket: `#{ticket_id}`)\n\n"
        f"👤 **Buyer:** {deal['buyer']}\n"
        f"👤 **Seller:** {deal['seller']}\n"
        f"📦 **Item:** {deal['item']}\n"
        f"💰 **Amount:** Rs {deal['amount']}\n"
        f"📊 **Status:** {deal['status']}\n"
        f"🕒 **Created At:** {deal['created_at']}\n"
        f"✅ **Completed At:** {deal['completed_at']}"
    )
    await message.reply_text(status_text)

@app.on_callback_query(filters.regex("dm_start_deal"))
async def dm_start_deal(client: Client, callback_query):
    user = callback_query.from_user
    chat_id = user.id
    await callback_query.answer()

    try:
        await client.send_message(chat_id, "Send your deal details in a single message following this format:\n\nBuyer: @buyer\nSeller: @seller\nItem: [Details]\nAmount: [Rs]\nTime: [Minutes]\nAdmin username: @admin")
        response = await client.ask(chat_id, "Please paste your details now:", timeout=300)
        text = response.text
    except Exception:
        await client.send_message(chat_id, "Deal creation timed out.")
        return

    await parse_and_create_deal(client, chat_id, text)

@app.on_message(filters.command("newdeal"))
async def process_new_deal(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.reply_text("⚠️ Only verified admins can create a deal using `/newdeal`!")
        return

    target_msg = message.reply_to_message
    if not target_msg or not target_msg.text:
        await message.reply_text("⚠️ Please reply to the deal details message with `/newdeal`.")
        return

    await parse_and_create_deal(client, message.chat.id, target_msg.text, reply_message=message)

async def parse_and_create_deal(client: Client, chat_id: int, text: str, reply_message: Message = None):
    lines = text.split("\n")
    buyer, seller, item_details, amount, time_limit, assigned_admin_username = "", "", "", "", 30, ""

    for line in lines:
        line_lower = line.lower()
        if "buyer:" in line_lower:
            buyer = line.split(":", 1)[1].strip()
        elif "seller:" in line_lower:
            seller = line.split(":", 1)[1].strip()
        elif "item:" in line_lower:
            item_details = line.split(":", 1)[1].strip()
        elif "amount:" in line_lower:
            amount = line.split(":", 1)[1].strip()
        elif "time:" in line_lower:
            try:
                time_limit = int(re.search(r'\d+', line).group())
            except:
                time_limit = 30
        elif "admin username:" in line_lower:
            assigned_admin_username = line.split(":", 1)[1].strip()

    if not buyer or not seller or not amount or not assigned_admin_username:
        await client.send_message(chat_id, "⚠️ Missing fields or invalid format.")
        return

    try:
        clean_username = assigned_admin_username.replace("@", "")
        admin_user = await client.get_users(clean_username)
        assigned_admin_id = admin_user.id
        admin_mention = admin_user.mention
    except Exception:
        await client.send_message(chat_id, f"⚠️ Could not resolve username `{assigned_admin_username}`.")
        return

    buyer_id, seller_id = 0, 0
    try:
        b_user = await client.get_users(buyer.replace("@", ""))
        buyer_id = b_user.id
    except:
        pass
    try:
        s_user = await client.get_users(seller.replace("@", ""))
        seller_id = s_user.id
    except:
        pass

    ticket_id = str(random.randint(100000, 999999))
    initial_buttons = [
        [InlineKeyboardButton("✅ Accept Deal", callback_data=f"accept_{ticket_id}")],
        [InlineKeyboardButton("🔴 Cancel Deal", callback_data=f"cancel_{ticket_id}")]
    ]

    deal_summary = (
        f"🛡️ **NEW ESCROW DEAL TICKET** (`#{ticket_id}`)\n\n"
        f"👤 **Buyer:** {buyer}\n"
        f"👤 **Seller:** {seller}\n"
        f"📦 **Item Details:** {item_details}\n"
        f"💰 **Amount:** Rs {amount}\n"
        f"⏱️ **Time Limit:** {time_limit} minutes\n"
        f"👮‍♂️ **Assigned Admin:** {admin_mention}\n\n"
        f"*Status: Waiting for {admin_mention} to Accept.*"
    )

    target_chat = ADMIN_GROUP_ID if ADMIN_GROUP_ID != 0 else chat_id
    if reply_message and target_chat == reply_message.chat.id:
        sent_msg = await reply_message.reply_text(deal_summary, reply_markup=InlineKeyboardMarkup(initial_buttons))
    else:
        sent_msg = await client.send_message(target_chat, deal_summary, reply_markup=InlineKeyboardMarkup(initial_buttons))
    
    deals_db[ticket_id] = {
        "ticket_id": ticket_id,
        "admin_id": assigned_admin_id,
        "buyer": buyer,
        "buyer_id": buyer_id,
        "seller": seller,
        "seller_id": seller_id,
        "item": item_details,
        "amount": amount,
        "time_limit": time_limit,
        "chat_id": target_chat,
        "status": "Waiting for Acceptance",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at": "Not Completed Yet",
        "release_triggered": False,
        "msg_id": sent_msg.id
    }
    await client.send_message(chat_id, f"✅ Deal ticket `#{ticket_id}` created successfully!")

@app.on_callback_query(filters.regex(r"accept_(\d+)"))
async def accept_deal(client: Client, callback_query):
    ticket_id = callback_query.data.split("_")[1]
    deal_info = deals_db.get(ticket_id)

    if not deal_info:
        await callback_query.answer("Deal data not found!", show_alert=True)
        return

    if callback_query.from_user.id != deal_info["admin_id"]:
        await callback_query.answer("Only the assigned admin can accept this deal!", show_alert=True)
        return

    await callback_query.answer("Deal accepted! Timer started.")
    deal_info["status"] = "Accepted & Running"
    
    updated_text = callback_query.message.text + f"\n\n🟢 **Status:** Accepted. Timer running!"
    release_buttons = [
        [InlineKeyboardButton("💸 Release Funds", callback_data=f"release_{ticket_id}")],
        [InlineKeyboardButton("🔴 Cancel Deal", callback_data=f"cancel_{ticket_id}")]
    ]
    await callback_query.message.edit_text(updated_text, reply_markup=InlineKeyboardMarkup(release_buttons))
    asyncio.create_task(deal_timer(client, deal_info["chat_id"], ticket_id, deal_info["time_limit"]))

@app.on_callback_query(filters.regex(r"(release|complete|cancel)_(\d+)"))
async def handle_admin_actions(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Only admins can perform this action!", show_alert=True)
        return

    action, ticket_id = callback_query.data.split("_")
    deal_info = deals_db.get(ticket_id)

    if not deal_info:
        await callback_query.answer("Deal not found!", show_alert=True)
        return

    if action == "release":
        deal_info["release_triggered"] = True
        deal_info["status"] = "Funds Released (5-min Payout Window)"
        await callback_query.answer("Funds release initiated!")
        
        updated_text = callback_query.message.text + "\n\n💸 **Funds Release Initiated.** 5-minute payout window started."
        complete_buttons = [
            [InlineKeyboardButton("✅ Completed", callback_data=f"complete_{ticket_id}")],
            [InlineKeyboardButton("🔴 Cancel Deal", callback_data=f"cancel_{ticket_id}")]
        ]
        await callback_query.message.edit_text(updated_text, reply_markup=InlineKeyboardMarkup(complete_buttons))
        await callback_query.message.reply_text(f"⏳ **5-Minute Payout Window Started for Ticket #{ticket_id}!** Admin must confirm payment and click **✅ Completed**.")
        asyncio.create_task(payout_timer(client, deal_info["chat_id"], ticket_id))

    elif action == "complete":
        deal_info["release_triggered"] = False
        deal_info["status"] = "Completed Successfully"
        deal_info["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        chat_id = deal_info["chat_id"]
        for uid in [deal_info["buyer_id"], deal_info["seller_id"]]:
            if uid:
                try:
                    await client.ban_chat_member(chat_id, uid)
                    await client.unban_chat_member(chat_id, uid)
                except Exception:
                    pass

        await callback_query.answer("Deal completed & users removed!")
        updated_text = callback_query.message.text + f"\n\n✅ **Status: Deal Completed Successfully!**\n🕒 Completed At: {deal_info['completed_at']}"
        await callback_query.message.edit_text(updated_text, reply_markup=None)

        if LOG_CHANNEL_ID != 0:
            log_text = (
                f"📋 **LOG: DEAL COMPLETED** (`#{ticket_id}`)\n\n"
                f"👤 **Buyer:** {deal_info['buyer']}\n"
                f"👤 **Seller:** {deal_info['seller']}\n"
                f"💰 **Amount:** Rs {deal_info['amount']}\n"
                f"✅ **Completed At:** {deal_info['completed_at']}"
            )
            try:
                await client.send_message(LOG_CHANNEL_ID, log_text)
            except Exception:
                pass

    elif action == "cancel":
        deal_info["status"] = "Cancelled"
        deal_info["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await callback_query.answer("Deal cancelled!")
        updated_text = callback_query.message.text + f"\n\n🔴 **Status: Deal Cancelled.**"
        await callback_query.message.edit_text(updated_text, reply_markup=None)

async def deal_timer(client: Client, chat_id: int, ticket_id: str, minutes: int):
    await asyncio.sleep(minutes * 60)
    deal_info = deals_db.get(ticket_id)
    if deal_info and deal_info["status"].startswith("Accepted"):
        deal_info["status"] = "Time Exceeded (Auto-refund)"
        await client.send_message(chat_id, f"🔴 **Time Limit Exceeded!** Deal `#{ticket_id}` failed. Auto-refund initiated.")

async def payout_timer(client: Client, chat_id: int, ticket_id: str):
    await asyncio.sleep(5 * 60)
    deal_info = deals_db.get(ticket_id)
    if deal_info and deal_info.get("release_triggered"):
        await client.send_message(chat_id, f"⚠️ **Payout Alert!** 5 minutes passed for Deal `#{ticket_id}`. Confirm payment and click **✅ Completed**!")

if __name__ == "__main__":
    app.run()

