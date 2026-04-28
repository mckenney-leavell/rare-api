# Create Post Sequence Diagram

Traces what happens from the moment a user clicks **Save** on the New Post form through to the database, including the optional image upload branch.

```mermaid
sequenceDiagram
    actor User
    participant PostCreate as PostCreate.js
    participant PostManager as PostManager.js
    participant api as api.js
    participant localStorage
    participant Django as Django (WSGI)
    participant DRF as DRF middleware
    participant authtoken as authtoken_token table
    participant view as post_views.py
    participant CategoryDB as Category table
    participant PostDB as Post table
    participant Serializer as PostDetailSerializer
    participant Filesystem as Filesystem (MEDIA_ROOT)

    User->>PostCreate: clicks Save button (type="submit")
    PostCreate->>PostCreate: handleSave(e) calls e.preventDefault()
    PostCreate->>PostManager: createPost(title + category_id + content)

    PostManager->>api: authHeader()
    api->>localStorage: getItem("auth_token")
    localStorage-->>api: token string
    api-->>PostManager: Authorization: Token value + Accept header

    PostManager->>Django: POST /posts with JSON body and auth token header

    Note over Django: CorsMiddleware checks origin (localhost:3000)
    Note over Django: AuthenticationMiddleware attaches request.user placeholder

    Django->>DRF: url matched to post_list() in rareapi/urls.py
    DRF->>authtoken: SELECT by token key value
    authtoken-->>DRF: token row containing user_id

    alt token not found or user inactive
        DRF-->>PostCreate: 401 Unauthorized
    else token valid
        DRF->>DRF: IsAuthenticated passes — request.user is RareUser instance
        DRF->>view: call post_list(request) for POST branch

        view->>CategoryDB: Category.objects.get(pk=category_id)

        alt category does not exist
            CategoryDB-->>view: DoesNotExist exception
            view-->>PostCreate: 400 — Invalid category
        else category found
            CategoryDB-->>view: Category instance

            view->>PostDB: Post.objects.create with user + category + title + content + publication_date + approved
            Note over view: approved = request.user.is_staff (True for admins / False for regular users)
            PostDB-->>view: Post instance with new id

            view->>Serializer: PostDetailSerializer(post).data
            Note over Serializer: Fetches post_tags via post_tags.select_related('tag').all()
            Note over Serializer: Nests UserSummarySerializer and CategorySerializer
            Serializer-->>view: id + title + content + publication_date + image_url + approved + user + category + tags

            view-->>Django: Response with serialized post — status 201
            Django-->>PostManager: HTTP 201 JSON
            PostManager-->>PostCreate: post object containing post.id
        end
    end

    PostCreate->>PostCreate: check fileRef.current.files[0]

    alt no file selected
        PostCreate->>PostCreate: navigate to /posts/post.id
    else file selected
        PostCreate->>PostCreate: build FormData and append image file
        PostCreate->>PostManager: uploadPostImage(post.id + formData)

        PostManager->>api: authHeader()
        api->>localStorage: getItem("auth_token")
        localStorage-->>api: token string
        api-->>PostManager: Authorization: Token value + Accept header

        Note over PostManager: No Content-Type header set — browser sets multipart boundary automatically
        PostManager->>Django: PUT /posts/id/image with multipart FormData body

        Django->>DRF: url matched to upload_post_image() in rareapi/urls.py
        DRF->>authtoken: SELECT by token key value
        authtoken-->>DRF: token row

        DRF->>view: call upload_post_image(request + pk)

        view->>PostDB: Post.objects.get(pk=pk)
        PostDB-->>view: Post instance

        view->>view: verify post.user equals request.user
        alt ownership mismatch
            view-->>PostCreate: 403 Forbidden
        else owner confirmed
            view->>view: verify image key present in request.FILES
            alt image missing from request
                view-->>PostCreate: 400 — No image provided
            else image present
                view->>Filesystem: makedirs MEDIA_ROOT/post_images then write file chunks
                Filesystem-->>view: file saved to disk

                view->>view: build absolute URL via request.build_absolute_uri()
                view->>PostDB: post.image_url = absolute_url then post.save()
                PostDB-->>view: row updated

                view-->>Django: Response with image_url — status 200
                Django-->>PostManager: HTTP 200 JSON
                PostManager-->>PostCreate: object with image_url
                PostCreate->>PostCreate: navigate to /posts/post.id
            end
        end
    end
```

## Participants

| Participant | File |
|---|---|
| `PostCreate.js` | [rare-client/src/components/posts/PostCreate.js](../../rare-client/src/components/posts/PostCreate.js) |
| `PostManager.js` | [rare-client/src/managers/PostManager.js](../../rare-client/src/managers/PostManager.js) |
| `api.js` | [rare-client/src/managers/api.js](../../rare-client/src/managers/api.js) |
| `post_list()` / `upload_post_image()` | [rare-api/rareapi/views/post_views.py](../rareapi/views/post_views.py) |
| `PostDetailSerializer` | [rare-api/rareapi/serializers/post_serializers.py](../rareapi/serializers/post_serializers.py) |
| URL routing | [rare-api/rareapi/urls.py](../rareapi/urls.py) |
| `Post` model | [rare-api/rareapi/models/post.py](../rareapi/models/post.py) |

## Key behaviours

- **Token auth**: DRF's `TokenAuthentication` resolves the `Authorization: Token <value>` header against the `authtoken_token` table on every request.
- **Moderation**: `approved` is set to `request.user.is_staff` at creation time — admin posts publish immediately, regular-user posts enter the moderation queue (`approved=False`).
- **Image upload is a separate request**: `createPost` returns first (HTTP 201), then `uploadPostImage` fires a `PUT` to `/posts/{id}/image` only if the user selected a file. The image is written to `MEDIA_ROOT/post_images/` and the absolute URL is persisted back to `post.image_url`.
- **Navigation**: the React component redirects to `/posts/{id}` after both requests complete (or after the first if no file was selected).
