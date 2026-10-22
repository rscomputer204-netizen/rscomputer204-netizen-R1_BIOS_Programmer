import os
import json
import re
import datetime
import time

def get_latest_transcript():
    user_home = os.path.expanduser("~")
    # Gemini IDE এর লগ ফোল্ডার থেকে চ্যাট হিস্ট্রি বের করা
    brain_dir = os.path.join(user_home, ".gemini", "antigravity-ide", "brain")
    
    if not os.path.exists(brain_dir):
        return None, None
        
    latest_file = None
    latest_time = 0
    latest_session = None
    
    for d in os.listdir(brain_dir):
        session_dir = os.path.join(brain_dir, d)
        if not os.path.isdir(session_dir):
            continue
            
        log_file = os.path.join(session_dir, ".system_generated", "logs", "transcript_full.jsonl")
        if os.path.exists(log_file):
            mtime = os.path.getmtime(log_file)
            if mtime > latest_time:
                latest_time = mtime
                latest_file = log_file
                latest_session = d
                
    return latest_file, latest_session

def save_chat_history():
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    daily_file = f"chat_{date_str}.txt"
    state_file = ".chat_saver_state.json"
    
    log_file, session_id = get_latest_transcript()
    
    if not log_file:
        print("Error: Could not find any active chat session.")
        return

    # আগের স্টেট পড়া (যাতে একই চ্যাট দুবার সেভ না হয়)
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except:
            pass

    # প্রথমে চেক করা হচ্ছে আজকের ডেটের ফাইলটি আছে কিনা
    if not os.path.exists(daily_file):
        # যদি ফাইল না থাকে, তাহলে নতুন করে সব সেভ করার জন্য last_step রিসেট করে দেওয়া হচ্ছে
        last_step = -1
    else:
        # যদি ফাইল থাকে, তাহলে আগের স্টেট থেকে কন্টিনিউ করবে
        last_step = state.get(session_id, -1)
    
    new_chats = []
    highest_step = last_step
    
    # লগ ফাইল পড়ে নতুন চ্যাটগুলো এক্সট্র্যাক্ট করা
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                step_index = data.get("step_index", 0)
                
                # যদি এই মেসেজটি আগে সেভ হয়ে থাকে, তাহলে স্কিপ করবে
                if step_index <= last_step:
                    continue
                    
                source = data.get("source")
                step_type = data.get("type")
                content = data.get("content", "")
                created_at = data.get("created_at", "")
                
                time_prefix = ""
                if created_at:
                    try:
                        # UTC থেকে Local Time
                        dt_utc = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                        dt_local = dt_utc.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
                        time_prefix = f"[{dt_local.strftime('%I:%M %p')}] "
                    except Exception:
                        pass
                
                if source == "USER_EXPLICIT" and step_type == "USER_INPUT":
                    # <USER_REQUEST> এর ভেতরের অংশ বের করা
                    match = re.search(r'<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>', content, re.DOTALL)
                    user_text = match.group(1).strip() if match else content.strip()
                    if user_text:
                        new_chats.append(f"{time_prefix}ME:\n{user_text}\n")
                        highest_step = max(highest_step, step_index)
                            
                elif source == "MODEL" and step_type == "PLANNER_RESPONSE":
                    if content.strip():
                        new_chats.append(f"{time_prefix}AI:\n{content.strip()}\n")
                        highest_step = max(highest_step, step_index)
            except Exception as e:
                continue

    if not new_chats:
        # print("No new chat found to save! Everything is already up to date.")
        return

    # নতুন চ্যাটগুলো প্রতিদিনের ফাইলে অ্যাপেন্ড (যুক্ত) করা
    with open(daily_file, 'a', encoding='utf-8') as f:
        if last_step == -1:
            time_str = now.strftime("%I:%M %p")
            f.write("\n======================================================\n")
            f.write(f" New Chat Session Started at {time_str}\n")
            f.write("======================================================\n\n")
            
        for chat in new_chats:
            f.write(chat + "\n")
            
    # নতুন স্টেট সেভ করা
    state[session_id] = highest_step
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f)
        
    print(f"Success! {len(new_chats)} new messages have been automatically extracted and saved to '{daily_file}'.")

if __name__ == "__main__":
    print("--- Auto Chat Saver ---")
    try:
        interval_str = input("Enter the interval in seconds to capture chat (e.g., 60 for 1 min): ")
        interval = int(interval_str.strip())
        if interval <= 0:
            print("Interval must be greater than 0. Defaulting to 60 seconds.")
            interval = 60
    except ValueError:
        print("Invalid input. Defaulting to 60 seconds.")
        interval = 60
        
    print(f"Chat saver is now running in the background! It will automatically save new chats every {interval} seconds.")
    print("Press Ctrl+C to stop the script.\n")
    
    try:
        # প্রথমে একবার রান করবে
        save_chat_history()
        while True:
            time.sleep(interval)
            save_chat_history()
    except KeyboardInterrupt:
        print("\nAuto Chat Saver stopped.")
