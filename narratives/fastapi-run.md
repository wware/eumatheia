# The Running Application

The FastAPI server is already running for you!

## View the App

Look at the **App** pane - it's showing your live application!

Try these interactions:
1. **Add an item** with a custom name (type in the input field)
2. **Add an item** with NO name (leave input blank) - watch it generate a random 10-character name!
3. **Delete an item** using the delete button
4. **Refresh** the list to see all items
5. **Delete all** items at once

## What's Happening

Behind the scenes:
- FastAPI server running on port 8080
- SQLite database (`items.db`) storing all items
- Each item gets an auto-incrementing ID
- Random names use Python's `random.choices()` with lowercase letters
- Frontend makes REST API calls (`/items` endpoint)

The app demonstrates:
- **POST /items** - Create new item
- **GET /items** - List all items
- **DELETE /items/{id}** - Delete specific item
- **DELETE /items** - Delete all items
