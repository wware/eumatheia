# Exploring the API Documentation

FastAPI automatically generates beautiful, interactive API documentation!

## View the API Docs

Open these URLs in new browser tabs:
- **Swagger UI**: http://localhost:9000/docs
- **ReDoc**: http://localhost:9000/redoc

The Swagger UI lets you:
- See all available endpoints
- View request/response schemas
- **Try out** API calls directly in the browser!
- See example responses

## Try the Interactive Docs

In the Swagger UI (http://localhost:9000/docs):

1. Click on **POST /items** to expand it
2. Click "Try it out"
3. Edit the request body (leave name empty or fill it in)
4. Click "Execute"
5. See the response with the created item!

Then try:
- **GET /items** - See all items you've created
- **DELETE /items/{item_id}** - Delete a specific item
- **DELETE /items** - Clear everything

Watch the **App** pane update automatically as you make API calls!

## What You've Learned

- FastAPI project structure and routing
- Pydantic models for request/response validation
- SQLite database integration with Python
- RESTful API design patterns
- Auto-generated API documentation (Swagger & ReDoc)
- Frontend-backend integration
- Random data generation for testing

**Congratulations!** You've explored a complete production-ready CRUD application with FastAPI.
