# FinancialTracker

Personal desktop finance tracker built with [Flet](https://flet.dev).

## Setup

```
uv sync
```

## Usage

```
uv run flet run              # run the app (dev mode, hot reload)
uv run pytest                # run tests
```

## Logging expenses from your iPhone

Expenses can be captured on your phone with an Apple Shortcut and picked up by the app the next
time it starts. Nothing is entered into your books automatically: on launch, the app shows a
review dialog where every pending entry can be corrected, re-assigned, or discarded first.

There is no server and no third-party service involved. The phone and the Mac exchange a plain
file through iCloud Drive:

```
iCloud Drive/Financial Tracker/
  inbox.jsonl       written by the Shortcut, drained by the app
  imported.jsonl    what was imported (last 1000 lines)
  rejected.jsonl    unreadable or discarded entries (last 1000 lines)
  categories.txt    written by the app - one category per line, the Shortcut's picker
  profiles.txt      written by the app - one profile per line
```

Run the app once first. It creates that folder, writes `categories.json` / `profiles.json` for
the Shortcut's pickers, and seeds an empty `inbox.jsonl` - the Shortcut appends by reading that
file and saving it back, so it has to exist before the first run.

This needs iCloud Drive to actually be enabled (**System Settings → Apple Account → iCloud →
iCloud Drive**). If it isn't, the app leaves the folder alone rather than creating a local one
that never syncs, and says so in the log.

### Building the Shortcut

Both pickers are read out of the app, so neither the category list nor the profile list ever has
to be kept in step by hand. In the Shortcuts app, tap **+** and add these in order.

**Category picker**

1. **Get File** - *Service* **iCloud Drive**, **Show Document Picker** off, *File Path*
   `/Financial Tracker/categories.txt`
2. **Get Text from Input** - the file from step 1
3. **Split Text** - the text from step 2, *Separator* **New Lines**
4. **Choose from List** - the list from step 3, prompt `Category`
5. **Set Variable** - name it `Cat`, value **Chosen Item**

**Profile picker**

6. **Get File** - same settings, *File Path* `/Financial Tracker/profiles.txt`
7. **Get Text from Input** - the file from step 6
8. **Split Text** - *Separator* **New Lines**
9. **Choose from List** - prompt `Profile`
10. **Set Variable** - name it `Prof`, value **Chosen Item**

**Amount and description**

11. **Ask for Input** - *Input Type* **Number**, prompt `Amount`
12. **Set Variable** - name it `Amt`, value **Provided Input**
13. **Ask for Input** - *Input Type* **Text**, prompt `Description`
14. **Set Variable** - name it `Desc`, value **Provided Input**

**Write the line**

15. **Text** - paste this, replacing each `<...>` with the variable of that name from the
    suggestion bar:

    ```
    {"amount":"<Amt>","category":"<Cat>","description":"<Desc>","profile":"<Prof>"}
    ```

    Keep the quotes exactly as shown, **including the ones around `<Amt>`**. The Number field
    formats using your phone's locale, so on a comma-decimal device it produces `58,7`, which
    unquoted is not valid JSON. Quoted, it is read with the same convention as every amount
    field in the app: `,` for decimals, `.` for thousands.

16. **Append to Text File** - *Service* **iCloud Drive**, *File Path*
    `/Financial Tracker/inbox.jsonl`, **Make New Line** on

Name it something short ("Log expense"), then add it to your Home Screen or run it with Siri.

Notes on the actions:

- **The five `Set Variable` steps are the point of this layout.** Two **Choose from List**
  actions both output a variable called *Chosen Item*, and two **Ask for Input** actions both
  output *Provided Input* - so without distinct names it is very easy for the Text action to
  pick up the wrong one and file every expense under the wrong category or profile. Naming them
  makes step 15 unambiguous. (If you'd rather keep it to 11 actions, you can instead tap each
  magic variable in step 15 and rename it there, but it's fiddlier to get right.)
- Steps 2-3 are the dependable way to turn a file into a picker: **Split Text** by new lines
  produces a plain list, which is why the app exports these as line-per-entry text rather than
  JSON. Do not use **Get Dictionary from Input** - it builds a dictionary, and **Choose from
  List** then shows keys with value previews instead of a flat list of names.
- File paths in **Get File** and **Append to Text File** are relative to the **iCloud Drive
  root**, so `/Financial Tracker/...` is the folder this app creates.
- Run the Mac app once before building this, so both `.txt` files exist.
- Add or rename a category or create a new profile, and the pickers follow on the app's next
  launch with nothing to change on the phone.
- There is still no date here: the app stamps the entry with today's date. To send one
  explicitly, see below.

### Notes on the format

- One JSON object per line. Only `amount` and `category` are required.
- `date` is optional and defaults to today. If given it must be ISO `YYYY-MM-DD`, and its
  **year decides which database the expense lands in** - so a New Year's Eve expense imported
  in January still goes to the right year. To send it, add a **Format Date** action with a
  custom format of `yyyy-MM-dd` and include `"date":"<Formatted Date>"`.
- `profile` is optional and defaults to `Personal`, though the Shortcut above always sends it.
  A profile that has no data yet won't appear in `profiles.txt` (it lists profiles that already
  have a database), so create it once in the app before logging to it from the phone.
- `amount` can be a JSON number (`12.5`, dot-decimal, as JSON requires) or a **string**. A
  string follows the app's own display convention - `.` for thousands and `,` for decimals - and
  may contain arithmetic, e.g. `"12,50 + 3"`. Beware that the string `"12.50"` therefore means
  *twelve hundred fifty*.
- Quoting the amount, as the Shortcut above does, is what makes a comma-decimal phone work. If
  an amount does slip through unquoted (`"amount":58,7`), the app quotes it and reads it as
  `58,7` rather than rejecting the line - but the quotes in the Shortcut are the real fix.
- `description` is optional. `type` is optional too, and reserved for future entry kinds;
  if present, anything other than `"expense"` is ignored.
- A line the app can't read is moved to `rejected.jsonl` rather than being retried forever.
  An entry you *skip* in the review dialog stays in `inbox.jsonl` and comes back next launch -
  only importing or explicitly discarding it removes it.
- Entries can also be reviewed on demand from **Settings → Maintenance → Import from iPhone**.

## App password

Optionally, the app can ask for a password at startup. Set one from **Settings → Require password
at startup** (minimum 10 characters, with at least one uppercase letter and one special character).
Three wrong attempts close the window.

This is a convenience lock, not encryption: the database files stay readable on disk to anyone with
filesystem access. It only stops someone who launches the app.

There is no in-app recovery. If you forget the password, clear it by hand:

```
sqlite3 ~/Library/Application\ Support/Financial\ Tracker/config.db \
  "DELETE FROM preferences WHERE key IN ('password_hash', 'password_salt');"
```

## Install as macOS app

See [Flet](https://flet.dev/docs/publish/macos/) for the prerequisite, then run:

```
uv run flet build macos
```

Builds `Financial Tracker.app` into `build/macos/`. Move it to `/Applications` to install.

## Requirements

Python >= 3.12
