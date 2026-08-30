import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import pyromod

# Configuration
API_ID = "YOUR_API_ID"
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 123456789  # Replace with your Telegram User ID

app = Client("escrow_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

ADMINS = [OWNER_ID]
COMMISSION_PERCENT = 5
active_deals = {}

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    instructions = (
        "**Welcome to Secure Escrow Service!** 🛡️\n\n"
        "**How to Use:**\n"
        "1. Type `/format` to see the correct single-message deal layout.\n"
        "2. Admins must reply/tag this format with `/newdeal` to register the deal.\n"
        "3. The assigned Admin must click **✅ Accept Deal** to start the timer.\n"
        "4. Once funds are released to the seller, a strict 5-minute payout window begins before marking **✅ Completed**.\n\n"
        "**Rules:** If the deal is not completed within the time limit, an auto-refund triggers."
    )
    
    buttons = [[InlineKeyboardButton("🟢 Start New Deal Instructions", callback_data="start_deal")]]
    
    for admin_id in ADMINS:
        try:
            user = await client.get_users(admin_id)
            name = user.first_name
        except:
            name = str(admin_id)
        buttons.append([InlineKeyboardButton(f"✅ Verified Admin: {name}", url=f"tg://user?id={admin_id}")])
    
    await message.reply_text(instructions, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("format"))
async def format_cmd(client, message):
    format_text = (
        "**📋 Escrow Deal Submission Format:**\n\n"
        "Reply to or tag this layout with `/newdeal` (Must be sent by an Admin):\n\n"
        "Buyer: @buyer_username\n"
        "Seller: @seller_username\n"
        "Item: Music Bot Code\n"
        "Amount: 500\n"
        "Time: 30\n"
        "Admin username: @admin_username"
    )
    await message.reply_text(format_text)

@app.on_message(filters.command("addadmin") & filters.user(ADMINS))
async def add_admin(client, message):
    if len(message.command) > 1:
        try:
            new_admin = int(message.command[1])
            if new_admin not in ADMINS:
                ADMINS.append(new_admin)
            await message.reply_text(f"Admin {new_admin} added! The Verified list updates automatically on /start.")
        except ValueError:
            await message.reply_text("Please provide a valid numeric User ID.")

@app.on_message(filters.command("add") & filters.user(ADMINS))
async def calculate_commission(client, message):
    text = message.text.lower()
    match = re.search(r'rs(\d+)', text)
    if match:
        amount = float(match.group(1))
        commission = (amount * COMMISSION_PERCENT) / 100
        await message.reply_text(
            f"**Deal Amount:** Rs {amount}\n"
            f"**Commission Fee (5%):** Rs {commission}\n"
            f"**Total to Collect:** Rs {amount + commission}"
        )
    else:
        await message.reply_text("Format incorrect. Use: `/add rs200`")

@app.on_message(filters.command("newdeal"))
async def process_new_deal(client, message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.reply_text("⚠️ Only verified admins can create a deal using `/newdeal`!")
        return

    target_msg = message.reply_to_message
    if not target_msg or not target_msg.text:
        await message.reply_text("⚠️ Please reply to the deal details message with `/newdeal`.")
        return

    lines = target_msg.text.split("\n")
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
        await message.reply_text("⚠️ Missing fields or invalid format in the tagged message. Use `/format` as a reference.")
        return

    try:
        clean_username = assigned_admin_username.replace("@", "")
        admin_user = await client.get_users(clean_username)
        assigned_admin_id = admin_user.id
        admin_mention = admin_user.mention
    except Exception:
        await message.reply_text(f"⚠️ Could not resolve username `{assigned_admin_username}`.")
        return

    deal_buttons = [
        [InlineKeyboardButton("✅ Accept Deal", callback_data=f"accept_{assigned_admin_id}")],
        [InlineKeyboardButton("💸 Release Funds", callback_data="release_funds"),
         InlineKeyboardButton("✅ Completed", callback_data="deal_complete")],
        [InlineKeyboardButton("🔴 Cancel Deal", callback_data="cancel_deal")]
    ]

    deal_summary = (
        f"🛡️ **NEW ESCROW DEAL TICKET** 🛡️\n\n"
        f"👤 **Buyer:** {buyer}\n"
        f"👤 **Seller:** {seller}\n"
        f"📦 **Item Details:** {item_details}\n"
        f"💰 **Amount:** Rs {amount}\n"
        f"⏱️ **Time Limit:** {time_limit} minutes\n"
        f"👮‍♂️ **Assigned Admin:** {admin_mention}\n\n"
        f"*Status: Waiting for {admin_mention} to click 'Accept Deal'.*"
    )

    sent_msg = await message.reply_text(deal_summary, reply_markup=InlineKeyboardMarkup(deal_buttons))
    
    active_deals[sent_msg.id] = {
        "admin_id": assigned_admin_id,
        "time_limit": time_limit,
        "amount": amount,
        "chat_id": message.chat.id,
        "release_triggered": False
    }

@app.on_callback_query(filters.regex(r"accept_(\d+)"))
async def accept_deal(client, callback_query):
    data_parts = callback_query.data.split("_")
    target_admin_id = int(data_parts[1])
    user_id = callback_query.from_user.id

    if user_id != target_admin_id:
        await callback_query.answer("Only the assigned admin can accept this deal!", show_alert=True)
        return

    msg_id = callback_query.message.id
    deal_info = active_deals.get(msg_id)

    await callback_query.answer("Deal accepted successfully! Timer started.")
    
    admin_user = callback_query.from_user
    updated_text = callback_query.message.text + f"\n\n🟢 **Status:** Accepted by {admin_user.mention}. Timer running!"
    await callback_query.message.edit_text(updated_text, reply_markup=callback_query.message.reply_markup)

    if deal_info:
        asyncio.create_task(deal_timer(client, deal_info["chat_id"], msg_id, deal_info["time_limit"]))

@app.on_callback_query(filters.regex("release_funds|deal_complete|cancel_deal"))
async def handle_admin_actions(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Only admins can perform this action!", show_alert=True)
        return

    action = callback_query.data
    msg_id = callback_query.message.id
    deal_info = active_deals.get(msg_id)

    if action == "release_funds":
        if deal_info:
            deal_info["release_triggered"] = True
        await callback_query.answer("Funds release initiated! 5-minute window started.")
        await callback_query.message.reply_text(
            "💸 **Funds Release Initiated** by Admin.\n"
            "⏳ **5-Minute Payout Window Started!** Admin must send payment to the seller and click **✅ Completed** within 5 minutes."
        )
        asyncio.create_task(payout_timer(client, callback_query.message.chat.id, msg_id))

    elif action == "deal_complete":
        if deal_info:
            deal_info["release_triggered"] = False  # Cancel payout timer warning if completed
        await callback_query.answer("Deal marked complete!")
        await callback_query.message.reply_text("✅ **Deal Completed Successfully!** All assets verified, payout sent, and deal closed.")

    elif action == "cancel_deal":
        await callback_query.answer("Deal cancelled!")
        await callback_query.message.reply_text("🔴 **Deal Cancelled** by Admin. Initiating standard safety protocol.")

async def deal_timer(client, chat_id, msg_id, minutes):
    await asyncio.sleep(minutes * 60)
    deal_info = active_deals.get(msg_id)
    if deal_info:
        await client.send_message(
            chat_id, 
            f"🔴 **Time Limit Exceeded!** The escrow deal (Msg ID: {msg_id}) failed to complete within {minutes} minutes. Auto-refund initiated to the buyer."
        )

async def payout_timer(client, chat_id, msg_id):
    await asyncio.sleep(5 * 60)  # 5 minutes
    deal_info = active_deals.get(msg_id)
    if deal_info and deal_info.get("release_triggered"):
        await client.send_message(
            chat_id, 
            f"⚠️ **Payout Alert!** 5 minutes have passed since 'Release Funds' was clicked for Deal ID {msg_id}. Please ensure payment has been sent to the seller and click **✅ Completed**!"
        )

if __name__ == "__main__":
    app.run()

