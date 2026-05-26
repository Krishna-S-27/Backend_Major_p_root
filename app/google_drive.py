"""
Google Drive integration for uploading videos
"""

import os
import logging
import mimetypes
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

google_drive_manager: Optional["GoogleDriveManager"] = None

def init_google_drive_manager(credentials_file: str) -> "GoogleDriveManager":
    global google_drive_manager
    google_drive_manager = GoogleDriveManager(credentials_file)
    return google_drive_manager


def get_google_drive_manager() -> Optional["GoogleDriveManager"]:
    return google_drive_manager


class GoogleDriveManager:
    """
    Manages Google Drive operations
    
    Features:
    - Upload videos to Drive
    - Create/manage folders
    - Generate sharing links
    """
    
    def __init__(self, credentials_file: str):
        """
        Initialize Google Drive manager
        
        @param credentials_file: Path to Google API credentials JSON
        """
        self.credentials_file = credentials_file
        self.service = None
        self.initialized = False
        
        if os.path.exists(credentials_file):
            try:
                self._initialize_service()
                self.initialized = True
                logger.info("✓ Google Drive initialized")
            except Exception as e:
                logger.warning(f"Google Drive initialization failed: {e}")
                logger.info("⚠️  Continuing without Google Drive support")
        else:
            logger.warning(f"Google Drive credentials not found: {credentials_file}")
            logger.info("⚠️  Continuing without Google Drive support")
    
    def _initialize_service(self):
        """Initialize Google Drive service"""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("✓ Google Drive service created")
            
        except ImportError:
            logger.warning("Google Drive libraries not installed")
            self.service = None
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Create folder in Google Drive
        
        @param folder_name: Name of folder
        @param parent_id: Parent folder ID
        @return: Folder ID or None
        """
        
        if not self.initialized or not self.service:
            logger.warning("Google Drive not initialized")
            return None
        
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"✓ Folder created: {folder_name} (ID: {folder_id})")
            return folder_id
            
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return None
    
    def upload_file(self, file_path: str, folder_id: Optional[str] = None) -> dict:
        """
        Upload file to Google Drive
        
        @param file_path: Path to file
        @param folder_id: Target folder ID
        @return: Upload result {'success': bool, 'file_id': str, 'link': str}
        """
        
        if not self.initialized or not self.service:
            logger.warning("Google Drive not initialized")
            return {
                'success': False,
                'error': 'Google Drive not initialized',
                'file_id': None,
                'link': None
            }
        
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': 'File not found',
                    'file_id': None,
                    'link': None
                }
            
            file_name = Path(file_path).name
            
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            from googleapiclient.http import MediaFileUpload
            mimetype, _ = mimetypes.guess_type(file_path)
            media_body = MediaFileUpload(
                file_path,
                mimetype=mimetype or 'application/octet-stream',
                resumable=True
            )

            upload_result = self.service.files().create(
                body=file_metadata,
                media_body=media_body,
                fields='id, webViewLink, parents'
            ).execute()

            file_id = upload_result.get('id')
            link = upload_result.get('webViewLink')
            
            logger.info(f"✓ File uploaded: {file_name} (ID: {file_id})")
            
            return {
                'success': True,
                'file_id': file_id,
                'link': link,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_id': None,
                'link': None
            }
    
    def share_file(self, file_id: str, email: str) -> bool:
        """
        Share file with email
        
        @param file_id: File ID
        @param email: Email to share with
        @return: Success status
        """
        
        if not self.initialized or not self.service:
            return False
        
        try:
            permission = {
                'type': 'user',
                'role': 'reader',
                'emailAddress': email
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            
            logger.info(f"✓ File shared with {email}")
            return True
            
        except Exception as e:
            logger.error(f"Share failed: {e}")
            return False
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete file from Google Drive
        
        @param file_id: File ID
        @return: Success status
        """
        
        if not self.initialized or not self.service:
            return False
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"✓ File deleted: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False