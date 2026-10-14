from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import Column, DateTime, Integer, String, func, text
from sqlalchemy.orm import Session

from database import Base, engine, get_db


class BlogCreate(BaseModel):
    title: str
    description: str
    city: str
    email: EmailStr
    author: str

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


class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    city = Column(String, nullable=False)
    email = Column(String, nullable=False)
    author = Column(String, nullable=False)
    date_created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def row_to_blog(blog: Blog) -> dict:
    return {
        "id": blog.id,
        "title": blog.title,
        "description": blog.description,
        "city": blog.city,
        "email": blog.email,
        "author": blog.author,
        "date_created": blog.date_created,
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


Base.metadata.create_all(bind=engine)
ensure_blog_description_column()

app = FastAPI(title="Blog API", description="API for managing blogs", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
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
    db_blog = Blog(
        title=blog.title,
        description=blog.description,
        city=blog.city,
        email=str(blog.email),
        author=blog.author,
    )
    db.add(db_blog)
    db.commit()
    db.refresh(db_blog)
    return row_to_blog(db_blog)


@app.put("/blogs/{blog_id}")
def update_blog_by_id(blog_id: int, blog: BlogUpdate, db: Session = Depends(get_db)):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
