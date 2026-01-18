from fastapi import APIRouter, Query, HTTPException, Request
from typing import List, Optional, Tuple, Any, Dict, Union
from Backend import db
from Backend.helper.database import convert_objectid_to_str
from Backend.helper.pyro import extract_languages_and_rip

router = APIRouter(tags=["Public API"])

@router.get("/api/tvshows", response_model=dict)
async def get_sorted_tv_shows(
    sort_by: List[str] = Query(default=["rating:desc"], description="List of fields to sort by. Format: field:direction"),
    page: int = Query(default=1, ge=1, description="Page number to return"),
    page_size: int = Query(default=10, ge=1, description="Number of TV shows per page")
):
    try:
        sort_params = [tuple(param.split(":")) for param in sort_by]
        result = await db.sort_tv_shows(sort_params, page, page_size)
        result["tv_shows"] = [await extract_languages_and_rip(doc) for doc in result.get("tv_shows", [])]
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/movies", response_model=dict)
async def get_sorted_movies(
    sort_by: List[str] = Query(default=["rating:desc"], description="List of fields to sort by. Format: field:direction"),
    page: int = Query(default=1, ge=1, description="Page number to return"),
    page_size: int = Query(default=10, ge=1, description="Number of movies per page")
):
    try:
        sort_params = [tuple(param.split(":")) for param in sort_by]
        result = await db.sort_movies(sort_params, page, page_size)
        result["movies"] = [await extract_languages_and_rip(doc) for doc in result.get("movies", [])]
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/id/{tmdb_id}", response_model=dict)
async def get_media_details(
    tmdb_id: int, 
    season_number: Optional[int] = Query(None), 
    episode_number: Optional[int] = Query(None)
) -> Union[dict, None]:
    """
    FastAPI endpoint to get details of a document, specific season, or episode
    by TMDB ID, season number, and episode number.
    """
    for db_index in range(1, db.current_db_index + 1):
        details = await db.get_media_details(
            tmdb_id=tmdb_id,
            db_index=db_index,
            season_number=season_number, 
            episode_number=episode_number
        )
        if details:
            return await extract_languages_and_rip(details)

    raise HTTPException(status_code=404, detail="Requested details not found")

@router.get("/api/similar/")
async def get_similar_media(
    tmdb_id: int,
    media_type: str = Query(..., regex="^(movie|tvshow)$"),
    page: int = Query(default=1, ge=1, description="Page number to return"),
    page_size: int = Query(default=10, ge=1, description="Number of similar media per page")
):
    """
    FastAPI endpoint to get similar movies or TV shows based on the parent tmdb_id, sorted by the number of genre matches and rating.
    
    :param tmdb_id: The TMDB ID of the parent movie or TV show.
    :param media_type: The media type ('movie' or 'tvshow').
    :param page: The page number to return.
    :param page_size: The number of similar media per page.
    :return: A dictionary containing the total count and a list of similar movies or TV shows.
    """
    result = await db.find_similar_media(tmdb_id=tmdb_id, media_type=media_type, page=page, page_size=page_size)
    result["similar_media"] = [await extract_languages_and_rip(doc) for doc in result.get("similar_media", [])]
    return result

@router.get("/api/search/", response_model=dict)
async def search_documents_endpoint(
    query: str = Query(..., description="Search query string"),
    page: int = Query(default=1, ge=1, description="Page number to return"),
    page_size: int = Query(default=10, ge=1, description="Number of documents per page")
):
    """
    FastAPI endpoint to search documents by title across TV and Movie collections,
    with pagination and total count.

    :param query: The search query string.
    :param page: The page number to return.
    :param page_size: The number of documents per page.
    :return: A dictionary containing the total count and a list of search results.
    """
    try:
        result = await db.search_documents(query=query, page=page, page_size=page_size)
        result["results"] = [await extract_languages_and_rip(doc) for doc in result.get("results", [])]
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))