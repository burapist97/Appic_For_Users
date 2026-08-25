# Appic_For_Users
Create your own Android mobile phone automation and more
📱 Appic Test Automation Studio – User Guide
Welcome to Appic! Appic is your personal assistant for automating mobile app tests. You don't need to be a coding expert to use it. If you can tap and swipe on a phone screen, you can create automated tests with Appic!

Follow this simple guide to start recording, editing, and running your tests in minutes.

🛠️ Step 1: Getting Ready
Before you begin, make sure your workspace is set up:

Connect your phone: Plug your Android phone into your computer using a USB cable.

Enable USB Debugging: Make sure "USB Debugging" is turned on in your phone's Developer Options.

Open the App: Launch the app you want to test on your phone.

Start Appic: Open the Appic Test Automation Studio on your computer.

📸 Step 2: Record Your First Test (New Visual Record)
This is where the magic happens! Appic will mirror your phone screen and record everything you do.

Starting the Recorder:
Click 📸 New Visual Record on the left menu.

Fill in the details at the top (Scenario Name is required!).

Click the green ▶️ START APPIC INSPECTOR button.

Wait a few seconds for your phone screen to appear on the left side of the window.

How to Control the Screen:
Appic captures your actions and saves them automatically. Just interact with the mirrored screen:

👆 Left Click (Tap): Click once on any button or icon. Appic will tap it on your phone and save the exact location.

↔️ Drag & Drop (Swipe): Click, hold, and drag your mouse up, down, left, or right to scroll through pages.

⌨️ Right Click (Type or Delete): Right-click on a text box (like a search bar or login field). A small menu will pop up:

Select ✍️ Type Text, type your word, and hit confirm.

Select 🧹 Clear Content to empty the box.

When you are done, click the red 🛑 Stop Record (ESC) button.

🧩 Step 3: Edit Your Test (Visual IDE)
Made a mistake? Want to add a pause? No problem!

Click 🧩 Visual IDE (Edit) on the left menu.

Select your recently recorded test from the dropdown menu at the top.

Here you will see all your steps as colorful blocks.

What you can do here:

Move Steps: Use the ⬆️ and ⬇️ arrows to reorder your actions.

Edit Steps: Click ✏️ Edit to change a typed text, adjust swipe directions, or change exactly what button is being clicked.

Delete Steps: Click the 🗑️ trash bin to remove an unwanted click.

Add Blocks manually: Click ➕ Add Block at the top if you forgot to add a step (like a Sleep/Wait timer or a physical system key like the Back button).

💾 Save: Always click Save Only when you finish editing!

▶️ Step 4: Run & Compare (Manage Tests)
It’s time to watch your phone test itself! Appic will repeat your exact actions and verify that the screen looks exactly as it should.

Click 📂 Manage Tests on the left menu.

Find your test in the list.

Click the green ▶️ Play & Compare button.

What happens next?
Appic will start controlling your phone. On your computer screen, you will see two panels:

Expected (Reference): How the screen looked when you first recorded it.

Current Device: How the screen looks right now.

Appic automatically compares these two images. If they match (85% similarity or higher), the step is a SUCCESS ✅. If the screen looks broken or different, it stops and marks it as an ERROR ❌ (highlighting the differences with red boxes).

(Note: If you are an advanced user, you can also click 📤 Export Script here to generate a clean, standard Python Appium script file!)

📊 Step 5: Check Your Results (Test Reports)
Keep track of all your test runs.

Click 📊 Test Reports on the left menu.

Green boxes mean the test passed perfectly. Red boxes mean something failed.

Click 🔍 Details to see exactly which step failed and view the error screenshot.

Click 📤 Download ZIP to save the full report, log files, and error images into one neat folder—perfect for sending to your developers!

💡 Pro Tips for Beginners:
Wait for the screen to load: When recording, after you click a button, give the app a second to load the next page before clicking again.

Use "Sleep" blocks: If your app takes a long time to load a certain page, go to the Visual IDE and add a Sleep block for 3 or 5 seconds to prevent the test from moving too fast.
