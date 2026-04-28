# System Architecture

## Overview

RARE is a content publishing platform (similar to Medium) built as a two-tier monolith: a React SPA frontend communicates with a Django REST API backend backed by a single PostgreSQL database.

## System Architecture Diagram

```mermaid
graph TB
    Browser["User / Browser"]

    subgraph Client["rare-client - React SPA - port 3000"]
        Router["React Router<br/>client-side routing"]
        Components["UI Components<br/>posts, users, comments,<br/>categories, tags, reactions, nav"]
        Managers["API Managers<br/>Auth, Post, User, Tag,<br/>Category, Comment, Subscription, Reaction"]
    end

    subgraph API["rare-api - Django REST Framework - port 8088"]
        URLRouter["URL Router<br/>rareapi/urls.py"]

        subgraph Views["Views"]
            AuthViews["auth_views<br/>/login  /register  /me"]
            PostViews["post_views<br/>/posts  /myposts  /approvedposts<br/>/unapprovedposts  /subscribedposts<br/>/posts/search  /posts/:id/approve"]
            UserViews["user_views<br/>/profiles  /profiles/:id<br/>/profiles/:id/deactivate  /profiles/:id/type"]
            CommentViews["comment_views<br/>/posts/:id/comments  /comments/:id"]
            CategoryViews["category_views<br/>/categories  /categories/:id"]
            TagViews["tag_views<br/>/tags  /tags/:id"]
            SubscriptionViews["subscription_views<br/>/profiles/:id/subscribe"]
            ReactionViews["reaction_views<br/>/reactions  /posts/:id/reactions"]
            AdminViews["admin_views<br/>/demotionqueue"]
        end

        Serializers["Serializers<br/>ORM objects to JSON"]
        Services["Services<br/>business logic layer"]
        ORM["Django ORM"]
    end

    subgraph Models["Data Models"]
        RareUser["RareUser<br/>extends AbstractUser<br/>bio, profile_image_url"]
        Post["Post<br/>title, content, image_url,<br/>publication_date, approved"]
        Category["Category<br/>label"]
        Tag["Tag / PostTag<br/>label"]
        Comment["Comment<br/>subject, content, created_on"]
        Subscription["Subscription<br/>follower, author,<br/>created_on, ended_on"]
        Reaction["Reaction / PostReaction<br/>label"]
        DemotionQueue["DemotionQueue<br/>action, admin, approver_one"]
    end

    subgraph Infra["Infrastructure - Docker"]
        Postgres[("PostgreSQL 16<br/>port 5432<br/>DB: rare")]
        Media["Local File System<br/>media/ directory<br/>profile and post images"]
    end

    Browser -- "HTTP port 3000" --> Router
    Router --> Components
    Components --> Managers
    Managers -- "HTTP REST + JSON / Bearer Token / port 8088" --> URLRouter

    URLRouter --> AuthViews
    URLRouter --> PostViews
    URLRouter --> UserViews
    URLRouter --> CommentViews
    URLRouter --> CategoryViews
    URLRouter --> TagViews
    URLRouter --> SubscriptionViews
    URLRouter --> ReactionViews
    URLRouter --> AdminViews

    AuthViews --> Serializers
    PostViews --> Serializers
    UserViews --> Serializers
    CommentViews --> Serializers
    CategoryViews --> Serializers
    TagViews --> Serializers
    SubscriptionViews --> Serializers
    ReactionViews --> Serializers
    AdminViews --> Serializers

    Serializers --> Services
    Services --> ORM

    ORM --> RareUser
    ORM --> Post
    ORM --> Category
    ORM --> Tag
    ORM --> Comment
    ORM --> Subscription
    ORM --> Reaction
    ORM --> DemotionQueue

    RareUser --> Postgres
    Post --> Postgres
    Category --> Postgres
    Tag --> Postgres
    Comment --> Postgres
    Subscription --> Postgres
    Reaction --> Postgres
    DemotionQueue --> Postgres

    PostViews -- "image upload" --> Media
    UserViews -- "image upload" --> Media
```

## Component Descriptions

| Component | Technology | Responsibility |
|---|---|---|
| **rare-client** | React 18, React Router 6, Bulma CSS | Single-page application; handles all UI and client-side routing |
| **API Managers** | Native `fetch()` | Thin HTTP client modules; attach Bearer token from `localStorage` and map to REST endpoints |
| **rare-api** | Django 4.2, Django REST Framework 3.15 | REST API server; enforces authentication, applies business logic, serializes responses |
| **URL Router** | Django URLconf | Maps URL patterns to view handlers |
| **Views** | DRF `APIView` subclasses | One module per domain (posts, users, comments, etc.); handles auth and permissions |
| **Serializers** | DRF `ModelSerializer` | Convert ORM model instances to/from JSON |
| **Services** | Plain Python | Isolate complex business logic (e.g., approval workflow, subscription feed) from views |
| **Django ORM** | Django ORM | Translates Python model operations to SQL queries |
| **PostgreSQL 16** | Docker container | Single relational database; all domain data |
| **Local File System** | Django `media/` | Stores uploaded profile and post images; served as static files in development |

## Key Flows

### Authentication
1. Client POSTs credentials to `/login` → API returns a DRF `Token`
2. Token stored in `localStorage`; every subsequent request includes `Authorization: Token <token>`
3. Admin users (`is_staff=True`) have posts auto-approved; regular users' posts enter a moderation queue

### Post Approval Workflow
1. Regular user creates a post → `approved=False`
2. Admin visits `/unapprovedposts` and calls `POST /posts/:id/approve`
3. Post becomes visible in `/approvedposts` and the subscription feed

### Image Uploads
- `PATCH /posts/:id/image` and `PATCH /profiles/:id/image` accept multipart form data
- Files are written to `rare-api/media/` on the server's local file system
