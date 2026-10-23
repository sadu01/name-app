from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import (Column, DateTime, Integer, String,ForeignKey, Table, func, text)
from sqlalchemy.orm import Session, relationship
from database import Base, engine, get_db

class UserCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_user_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        if not all(c.isalpha() or c.isspace() for c in value):
            raise ValueError("Name must contain only letters and spaces")
        return value

class BlogCreate(BaseModel):
    title: str
    description: str
    city: str
    email: EmailStr
    author: str
    tag_ids: list[int] = []
    user_id: int


    
    @field_validator("title", "city", "author")
    @classmethod
    def must_contain_letters_only(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("Only letters and spaces are allowed")
        return normalized

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description cannot be empty")
        return value.strip()


class BlogUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    email: Optional[EmailStr] = None
    author: Optional[str] = None
    user_id: Optional[int] = None

    @field_validator("title", "city", "author")
    @classmethod
    def must_contain_letters_only(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("Only letters and spaces are allowed")
        return normalized

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        normalized = value.strip()
        if not normalized:
            raise ValueError("Description cannot be empty")
        return value.strip()

    
blog_tags = Table(
    "blog_tags",
    Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)


class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    city = Column(String, nullable=False)
    email = Column(String, nullable=False)
    author = Column(String, nullable=False)
    date_created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)



    tags = relationship("Tag", secondary=blog_tags, back_populates="blogs")
    user_id = Column(Integer,ForeignKey("users.id"),nullable=True)



    user = relationship("User",back_populates="blogs")

    

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    profile = relationship("Profile",back_populates="user",uselist=False)

    blogs = relationship("Blog",back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer,ForeignKey("users.id"),unique=True,nullable=False)

    city = Column(String, nullable=False)

    user = relationship("User",back_populates="profile")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    blogs = relationship("Blog",secondary=blog_tags,back_populates="tags")




def row_to_blog(blog: Blog) -> dict:
    return {
        "id": blog.id,
        "title": blog.title,
        "description": blog.description,
        "city": blog.city,
        "email": blog.email,
        "author": blog.author,
        "date_created": blog.date_created,
        "user_id": blog.user_id,
        "user_name": blog.user.name if blog.user else None,
        "tags": [tag.name for tag in blog.tags]
    }
    


def ensure_blog_description_column() -> None:
    with engine.begin() as connection:
        column_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'blogs'
                      AND column_name = 'description'
                )
                """
            )
        ).scalar()

        if not column_exists:
            connection.execute(text("ALTER TABLE blogs ADD COLUMN description TEXT"))
            connection.execute(text("UPDATE blogs SET description = '' WHERE description IS NULL"))
            connection.execute(text("ALTER TABLE blogs ALTER COLUMN description SET NOT NULL"))


app = FastAPI(title="Blog API", description="API for managing blogs", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "https://name-app-frontend.onrender.com",

    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "API"}


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        database_name = db.execute(text("SELECT current_database()")).scalar_one()
        return {"status": "connected", "database": database_name}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database connection failed") from exc


@app.get("/blogs")
def get_blogs(db: Session = Depends(get_db)):
    blogs = db.query(Blog).order_by(Blog.id).all()
    return [row_to_blog(blog) for blog in blogs]


@app.get("/blogs/{blog_id}")
def get_blog_by_id(blog_id: int, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    return row_to_blog(blog)



@app.post("/blogs", status_code=201)
def add_blog(blog: BlogCreate, db: Session = Depends(get_db)):

    selected_user = db.query(User).filter(
        User.id == blog.user_id
    ).first()

    if selected_user is None:
        raise HTTPException(
            status_code=400,
            detail="Selected user does not exist"
        )

    db_blog = Blog(
        title=blog.title,
        description=blog.description,
        city=blog.city,
        email=str(blog.email),
        author=blog.author,
        user_id=selected_user.id,
    )

    tag_ids = list(set(blog.tag_ids))

    if tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()

        if len(tags) != len(tag_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more tag IDs are invalid"
            )

        db_blog.tags = tags

   
    db.add(db_blog)
    db.commit()
    db.refresh(db_blog)

    return row_to_blog(db_blog)




@app.put("/blogs/{blog_id}")
def update_blog_by_id(
    blog_id: int,
    blog: BlogUpdate,
    db: Session = Depends(get_db)
):
    existing = db.query(Blog).filter(Blog.id == blog_id).first()

    if existing is None:
        raise HTTPException(status_code=404, detail="Blog not found")

    if blog.title is not None:
        existing.title = blog.title

    if blog.description is not None:
        existing.description = blog.description

    if blog.city is not None:
        existing.city = blog.city

    if blog.email is not None:
        existing.email = str(blog.email)

    if blog.author is not None:
        existing.author = blog.author

    if blog.user_id is not None:
        selected_user = db.query(User).filter(
            User.id == blog.user_id
        ).first()

        if selected_user is None:
            raise HTTPException(
                status_code=400,
                detail="Selected user does not exist"
            )

        existing.user_id = selected_user.id

    db.commit()
    db.refresh(existing)

    return row_to_blog(existing)


@app.delete("/blogs/{blog_id}")
def delete_blog_by_id(blog_id: int, db: Session = Depends(get_db)):
    existing = db.query(Blog).filter(Blog.id == blog_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Blog not found")

    db.delete(existing)
    db.commit()
    return {"message": "Blog deleted successfully", "deleted": row_to_blog(existing)}


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()

    return [
        {
            "id": user.id,
            "name": user.name
        }
        for user in users
    ]

@app.post("/users", status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="User name cannot be empty"
        )

    new_user = User(name=name)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "name": new_user.name
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
