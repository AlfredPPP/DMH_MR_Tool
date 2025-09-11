# src/dmh_mr_tool/business/services/parser_service.py
"""Service for parsing PDF and Excel files with various templates"""

import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pdfplumber  # PyMuPDF
import pandas as pd
import openpyxl

from database.connection import DatabaseManager
from database.models import ParseTemplateMR, ParseTemplateNZ, ColumnMap
from config.settings import CONFIG
from ui.utils.signal_bus import signalBus

import structlog

logger = structlog.get_logger()


class ParserService:
    """Service for parsing financial documents"""

    _instance = None
    _db_manager = None

    def __new__(cls):
        """Singleton pattern for service"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize service with database manager"""
        if not self._initialized:
            self._ensure_db_manager()
            self.templates_cache = {}
            self.column_map_cache = {}
            self._load_column_mappings()
            self._initialized = True

    def _ensure_db_manager(self):
        """Ensure database manager is initialized"""
        if ParserService._db_manager is None:
            ParserService._db_manager = DatabaseManager(CONFIG.database)
            ParserService._db_manager.initialize()

    @property
    def db_manager(self):
        """Get database manager instance"""
        return ParserService._db_manager

    def _load_column_mappings(self):
        """Load column mappings from database"""
        with self.db_manager.session() as session:
            mappings = session.query(ColumnMap).filter(
                ColumnMap.is_valid == True
            ).all()

            for mapping in mappings:
                self.column_map_cache[mapping.d_code] = {
                    'v_code': mapping.v_code,
                    'v_desc': mapping.v_desc,
                    'd_code': mapping.d_code,
                    'd_desc': mapping.d_desc
                }

    def get_available_templates(self) -> List[str]:
        """Get list of available parsing templates"""
        templates = []

        with self.db_manager.session() as session:
            # Get MR templates
            mr_templates = session.query(ParseTemplateMR.template_name).filter(
                ParseTemplateMR.is_valid == True
            ).distinct().all()

            templates.extend([t[0] for t in mr_templates])

            # Get NZ templates
            nz_templates = session.query(ParseTemplateNZ.template_name).filter(
                ParseTemplateNZ.is_valid == True
            ).distinct().all()

            templates.extend([t[0] for t in nz_templates])

        # Add default templates
        default_templates = [
            'vanguard_au', 'asx_nz & tax_marker', 'asx_dividend',
            'perpetual', 'Hi-Trust UR'
        ]

        for template in default_templates:
            if template not in templates:
                templates.append(template)

        return sorted(list(set(templates)))

    def get_available_fields(self) -> List[str]:
        """Get list of available field descriptions"""
        return [mapping['d_desc'] for mapping in self.column_map_cache.values()]

    def get_template_data(self, template_name: str) -> Dict[str, str]:
        """Get template patterns for a specific template"""
        template_data = {}

        with self.db_manager.session() as session:
            # Try MR template first
            mr_template = session.query(ParseTemplateMR).filter(
                ParseTemplateMR.template_name == template_name,
                ParseTemplateMR.is_valid == True
            ).first()

            if mr_template:
                # Get all column attributes
                for column in ParseTemplateMR.__table__.columns:
                    if column.name not in ['id', 'template_name', 'is_valid', 'update_timestamp']:
                        value = getattr(mr_template, column.name)
                        if value:
                            template_data[column.name] = value
            else:
                # Try NZ template
                nz_template = session.query(ParseTemplateNZ).filter(
                    ParseTemplateNZ.template_name == template_name,
                    ParseTemplateNZ.is_valid == True
                ).first()

                if nz_template:
                    for column in ParseTemplateNZ.__table__.columns:
                        if column.name not in ['id', 'template_name', 'is_valid', 'update_timestamp']:
                            value = getattr(nz_template, column.name)
                            if value:
                                template_data[column.name] = value

        return template_data

    async def parse_file(self, file_path: str, template_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Parse a file using the specified template

        Returns:
            Dictionary with field_name -> {value, comment, d_desc}
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get template data
        template_data = self.get_template_data(template_name)

        # Parse based on file type
        if file_path.suffix.lower() == '.pdf':
            return await self._parse_pdf(file_path, template_data, template_name)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            return await self._parse_excel(file_path, template_data, template_name)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

    async def _parse_pdf(self, file_path: Path, template_data: Dict, template_name: str) -> Dict[str, Dict[str, Any]]:
        """Parse PDF file"""
        results = {}

        try:
            full_text = ""
            with pdfplumber.open(str(file_path)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"

            # Apply regex patterns from template
            for field_name, pattern in template_data.items():
                if pattern and not pattern.startswith('='):  # Skip formula patterns
                    try:
                        match = re.search(pattern, full_text, re.MULTILINE | re.DOTALL)
                        if match:
                            value = match.group(1) if match.groups() else match.group(0)

                            # Clean the value
                            value = value.strip()

                            # Try to convert to appropriate type
                            if field_name in ['income_rate', 'tax_rate', 'franked_pct', 'unfranked_pct']:
                                try:
                                    value = float(value)
                                except ValueError:
                                    pass
                            elif field_name in ['ex_date', 'pay_date', 'pub_date']:
                                # Try to parse date
                                value = self._parse_date(value)

                            results[field_name] = {
                                'value': value,
                                'comment': '',
                                'd_desc': self.column_map_cache.get(field_name, {}).get('d_desc', field_name)
                            }
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern for {field_name}: {e}")

            # Apply business rules for calculated fields
            results = self._apply_business_rules(results, template_name)

            # Add fields that weren't found as None
            for field_name in self.column_map_cache.keys():
                if field_name not in results:
                    results[field_name] = {
                        'value': None,
                        'comment': '',
                        'd_desc': self.column_map_cache.get(field_name, {}).get('d_desc', field_name)
                    }

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise

        return results

    async def _parse_excel(self, file_path: Path, template_data: Dict, template_name: str) -> Dict[str, Dict[str, Any]]:
        """Parse Excel file"""
        results = {}

        try:
            # Read Excel file
            df = pd.read_excel(file_path)

            # For Excel files, try to match column headers with field names
            for field_name in template_data.keys():
                # Look for matching column
                field_desc = self.column_map_cache.get(field_name, {}).get('d_desc', field_name)

                # Try exact match first
                if field_desc in df.columns:
                    value = df[field_desc].iloc[0] if not df[field_desc].empty else None
                    results[field_name] = {
                        'value': value,
                        'comment': '',
                        'd_desc': field_desc
                    }
                else:
                    # Try partial match
                    for col in df.columns:
                        if field_desc.lower() in col.lower() or col.lower() in field_desc.lower():
                            value = df[col].iloc[0] if not df[col].empty else None
                            results[field_name] = {
                                'value': value,
                                'comment': 'Matched by partial column name',
                                'd_desc': field_desc
                            }
                            break

            # Apply business rules
            results = self._apply_business_rules(results, template_name)

            # Add missing fields
            for field_name in self.column_map_cache.keys():
                if field_name not in results:
                    results[field_name] = {
                        'value': None,
                        'comment': '',
                        'd_desc': self.column_map_cache.get(field_name, {}).get('d_desc', field_name)
                    }

        except Exception as e:
            logger.error(f"Error parsing Excel: {e}")
            raise

        return results

    def _apply_business_rules(self, results: Dict, template_name: str) -> Dict:
        """Apply business rules for calculated fields"""

        # Example business rules based on template
        if template_name == 'asx_mit_notice':
            # Tax rate default
            if 'tax_rate' not in results or results['tax_rate']['value'] is None:
                results['tax_rate'] = {
                    'value': 0.3,
                    'comment': 'Default value per client specific',
                    'd_desc': self.column_map_cache.get('tax_rate', {}).get('d_desc', 'Tax Rate')
                }

        elif template_name == 'vanguard_au':
            # Calculate total from components
            total = 0
            for field in ['DOM_INC', 'FOR_INC', 'DOM_DID']:
                if field in results and results[field]['value']:
                    try:
                        total += float(results[field]['value'])
                    except (ValueError, TypeError):
                        pass

            if total > 0:
                results['TOTAL'] = {
                    'value': total,
                    'comment': 'Sum of DOM_INC + FOR_INC + DOM_DID',
                    'd_desc': 'Total Distribution'
                }

        elif template_name == 'Hi-Trust UR':
            # Special handling for Hi-Trust UR template
            # This template is for batch processing actual values
            pass

        return results

    def _parse_date(self, date_str: str) -> datetime.date:
        """Parse date from various formats"""
        if not date_str:
            return None

        # Common date formats
        formats = [
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d %b %Y',
            '%d %B %Y',
            '%Y%m%d'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # If no format matches, return as string
        return date_str

    async def batch_parse_folder(self, folder_path: str, template_name: str = 'Hi-Trust UR') -> List[Dict]:
        """
        Parse all files in a folder with the specified template

        Returns:
            List of parsed results
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Invalid folder path: {folder_path}")

        results = []

        # Get all supported files
        files = []
        for ext in ['*.pdf', '*.xlsx', '*.xls']:
            files.extend(folder.glob(ext))

        total = len(files)
        for i, file_path in enumerate(files):
            try:
                # Emit progress signal
                if hasattr(signalBus, 'spiderProgressSignal'):
                    signalBus.spiderProgressSignal.emit('Batch Parse', i + 1, total)

                # Parse file
                parsed = await self.parse_file(str(file_path), template_name)

                results.append({
                    'file': str(file_path),
                    'data': parsed,
                    'success': True
                })

            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                results.append({
                    'file': str(file_path),
                    'error': str(e),
                    'success': False
                })

        # Emit completion signal
        if hasattr(signalBus, 'parserCompleteSignal'):
            signalBus.parserCompleteSignal.emit(True, {'count': len(results)})

        return results

    def validate_parse_results(self, results: Dict) -> tuple[bool, List[str]]:
        """
        Validate parse results

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        required_fields = ['ex_date', 'pay_date', 'asset_id']

        for field in required_fields:
            if field not in results or results[field].get('value') is None:
                errors.append(f"Missing required field: {field}")

        # Validate data types
        numeric_fields = ['income_rate', 'tax_rate', 'franked_pct', 'unfranked_pct']

        for field in numeric_fields:
            if field in results and results[field].get('value') is not None:
                try:
                    float(results[field]['value'])
                except (ValueError, TypeError):
                    errors.append(f"Invalid numeric value for {field}")

        # Validate dates
        date_fields = ['ex_date', 'pay_date', 'pub_date']

        for field in date_fields:
            if field in results and results[field].get('value') is not None:
                value = results[field]['value']
                if not isinstance(value, (datetime, datetime.date)):
                    errors.append(f"Invalid date format for {field}")

        return len(errors) == 0, errors

    def get_template_by_file_pattern(self, filename: str) -> Optional[str]:
        """
        Auto-detect template based on filename patterns

        Args:
            filename: Name of the file

        Returns:
            Template name or None
        """
        filename_lower = filename.lower()

        # Pattern matching rules
        patterns = {
            'vanguard_au': ['vanguard', 'vgd', 'vgs', 'vas'],
            'asx_mit_notice': ['mit', 'notice', 'distribution'],
            'asx_dividend': ['dividend', 'div'],
            'perpetual': ['perpetual', 'ppt'],
            'Hi-Trust UR': ['hi-trust', 'hitrust', 'ur']
        }

        for template, keywords in patterns.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    return template

        return None