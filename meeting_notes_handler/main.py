#!/usr/bin/env python3
"""Meeting Notes Handler CLI - Main entry point."""

import sys
import logging
from pathlib import Path
from datetime import datetime
import click

from . import __version__
from .config import Config
from .google_meet_fetcher import GoogleMeetFetcher
from .file_organizer import FileOrganizer
from .series_tracker import MeetingSeriesTracker
from .content_hasher import ContentHasher
from .diff_engine import DiffEngine
from .content_cache import MeetingContentCache

def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

@click.group(invoke_without_command=True)
@click.option('--config', '-c', help='Configuration file path')
@click.option('--log-level', default='INFO', help='Logging level')
@click.option('--version', is_flag=True, help='Show version and exit')
@click.pass_context
def cli(ctx, config, log_level, version):
    """Meeting Notes Handler - Fetch and organize Google Meet notes."""
    if version:
        click.echo(f"Meeting Notes Handler v{__version__}")
        return
    
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    
    ctx.ensure_object(dict)
    
    setup_logging(log_level)
    
    try:
        ctx.obj['config'] = Config(config)
        logger = logging.getLogger(__name__)
        logger.info("Meeting Notes Handler initialized")
    except Exception as e:
        click.echo(f"Error initializing configuration: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--days', '-d', default=None, type=int, help='Number of days back to fetch')
@click.option('--dry-run', is_flag=True, help='Preview without saving files')
@click.option('--week', '-w', help='Specific week to fetch (YYYY-WW format)')
@click.option('--accepted', is_flag=True, default=False, help='Only fetch notes from meetings you accepted or are tentative for.')
@click.option('--declined', is_flag=True, default=False, help='Only fetch notes from meetings you declined.')
@click.option('--force', '-f', is_flag=True, default=False, help='Force re-fetch meetings even if already processed')
@click.option('--gemini-only', '-g', is_flag=True, default=False, help='Only fetch Gemini notes and transcripts, skip other documents')
@click.option('--smart-filter', '-s', is_flag=True, default=False, help='Apply smart content filtering to extract only new content from recurring meetings')
@click.option('--diff-mode', is_flag=True, default=False, help='Only save new content compared to previous meetings')
@click.pass_context
def fetch(ctx, days, dry_run, week, accepted, declined, force, gemini_only, smart_filter, diff_mode):
    """Fetch meeting notes from Google Calendar and Docs."""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    # Validate mutually exclusive options
    if accepted and declined:
        click.echo("❌ Error: --accepted and --declined options are mutually exclusive", err=True)
        sys.exit(1)
    
    if week:
        click.echo(f"Week-specific fetching not yet implemented: {week}")
        return
    
    click.echo("🔍 Fetching meeting notes...")
    if dry_run:
        click.echo("📋 DRY RUN - No files will be saved")
    if accepted:
        click.echo("✅ Filtering for accepted meetings only")
    if declined:
        click.echo("❌ Filtering for declined meetings only")
    if force:
        click.echo("🔄 FORCE MODE - Will re-fetch already processed meetings")
    if gemini_only:
        click.echo("🤖 GEMINI MODE - Only fetching Gemini notes and transcripts")
    if smart_filter:
        click.echo("🧠 SMART FILTER - Extracting only new content from recurring meetings")
    if diff_mode:
        click.echo("🔍 DIFF MODE - Only saving new content compared to previous meetings")

    try:
        fetcher = GoogleMeetFetcher(config)
        
        click.echo("🔐 Authenticating with Google APIs...")
        if not fetcher.authenticate():
            click.echo("❌ Authentication failed", err=True)
            sys.exit(1)
        
        click.echo("✅ Authentication successful")
        
        # Fetch and process meetings
        results = fetcher.fetch_and_process_all(
            days_back=days, 
            dry_run=dry_run, 
            accepted_only=accepted, 
            declined_only=declined,
            force_refetch=force, 
            gemini_only=gemini_only, 
            smart_filtering=smart_filter,
            diff_mode=diff_mode
        )
        
        if results['success']:
            click.echo(f"\n📊 Results:")
            click.echo(f"   Meetings found: {results['meetings_found']}")
            click.echo(f"   Meetings processed: {results['meetings_processed']}")
            if results.get('meetings_skipped', 0) > 0:
                click.echo(f"   Meetings skipped (already processed): {results['meetings_skipped']}")
            click.echo(f"   Meetings with notes: {results['meetings_with_notes']}")
            click.echo(f"   Total documents: {results['total_documents']}")
            
            if not dry_run:
                click.echo(f"   📁 Notes saved to: {config.output_directory}")
            
            # Show details of processed meetings
            if results['processed_meetings']:
                click.echo(f"\n📝 Processed meetings:")
                for meeting in results['processed_meetings']:
                    if meeting.get('skipped'):
                        status = "⏭️ "
                        date_str = datetime.fromisoformat(meeting['date']).strftime('%Y-%m-%d %H:%M')
                        click.echo(f"   {status} {date_str} - {meeting['title']} (skipped: {meeting.get('reason', 'already processed')})")
                    else:
                        status = "✅" if meeting['success'] else "❌"
                        date_str = datetime.fromisoformat(meeting['date']).strftime('%Y-%m-%d %H:%M')
                        click.echo(f"   {status} {date_str} - {meeting['title']} ({meeting['notes_count']} docs)")
            
            # Show errors if any
            if results['errors']:
                click.echo(f"\n⚠️  Errors encountered:")
                for error in results['errors']:
                    click.echo(f"   • {error}")
        else:
            click.echo(f"❌ Failed: {results.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error during fetch operation: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def list_weeks(ctx):
    """List all available weeks with meeting notes."""
    config = ctx.obj['config']
    
    organizer = FileOrganizer(config.output_directory)
    weeks = organizer.list_weeks()
    
    if not weeks:
        click.echo("📂 No meeting notes found")
        return
    
    click.echo(f"📅 Available weeks ({len(weeks)} total):")
    for week in weeks:
        meetings = organizer.list_meetings_in_week(week)
        click.echo(f"   {week}: {len(meetings)} meetings")

@cli.command()
@click.argument('week')
@click.pass_context
def list_meetings(ctx, week):
    """List meetings in a specific week."""
    config = ctx.obj['config']
    
    organizer = FileOrganizer(config.output_directory)
    meetings = organizer.list_meetings_in_week(week)
    
    if not meetings:
        click.echo(f"📂 No meetings found for week {week}")
        return
    
    click.echo(f"📝 Meetings in week {week} ({len(meetings)} total):")
    for meeting_file in meetings:
        file_size = meeting_file.stat().st_size
        modified = datetime.fromtimestamp(meeting_file.stat().st_mtime)
        click.echo(f"   📄 {meeting_file.name} ({file_size} bytes, modified {modified.strftime('%Y-%m-%d %H:%M')})")

@cli.command()
@click.pass_context
def setup(ctx):
    """Setup Google API credentials and configuration."""
    config = ctx.obj['config']
    
    click.echo("🔧 Setting up Meeting Notes Handler")
    click.echo("\nChoose your preferred authentication method:")
    click.echo("\n1. 🚀 Google CLI (Recommended - Easiest)")
    click.echo("2. 📁 Manual credentials file")
    
    choice = click.prompt("Select option", type=click.Choice(['1', '2']), default='1')
    
    if choice == '1':
        click.echo("\n🚀 Setting up with Google CLI...")
        click.echo("\nIf you don't have gcloud CLI installed:")
        click.echo("   curl https://sdk.cloud.google.com | bash")
        click.echo("   exec -l $SHELL")
        click.echo("\nRun these commands:")
        click.echo("   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly")
        click.echo("   gcloud services enable calendar-json.googleapis.com")
        click.echo("   gcloud services enable drive.googleapis.com") 
        click.echo("   gcloud services enable docs.googleapis.com")
        
        if click.confirm("\nHave you completed the gcloud setup?"):
            # Test authentication
            click.echo("\n🔐 Testing authentication...")
            try:
                fetcher = GoogleMeetFetcher(config)
                if fetcher.authenticate():
                    click.echo("✅ Authentication successful!")
                    click.echo("\n🎉 Setup complete! You can now use 'fetch' to get meeting notes.")
                else:
                    click.echo("❌ Authentication failed", err=True)
                    click.echo("Please ensure you've run the gcloud commands above.")
            except Exception as e:
                click.echo(f"❌ Error during authentication test: {e}", err=True)
    
    else:
        click.echo("\n📁 Manual credentials setup...")
        click.echo("This requires Google Cloud Console setup:")
        click.echo("\n1. Go to: https://console.cloud.google.com/")
        click.echo("2. Create a project and enable APIs (Calendar, Drive, Docs)")
        click.echo("3. Create OAuth 2.0 credentials for desktop application")
        click.echo("4. Download the credentials JSON file")
        
        creds_path = click.prompt(f"\nPath to credentials JSON file", 
                                 default=str(config.google_credentials_file))
        
        creds_file = Path(creds_path)
        if not creds_file.exists():
            click.echo(f"❌ Credentials file not found: {creds_file}", err=True)
            return
        
        # Copy credentials to project directory if not already there
        if creds_file != config.google_credentials_file:
            import shutil
            shutil.copy2(creds_file, config.google_credentials_file)
            click.echo(f"📋 Copied credentials to: {config.google_credentials_file}")
        
        # Test authentication
        click.echo("\n🔐 Testing authentication...")
        try:
            fetcher = GoogleMeetFetcher(config)
            if fetcher.authenticate():
                click.echo("✅ Authentication successful!")
                click.echo("\n🎉 Setup complete! You can now use 'fetch' to get meeting notes.")
            else:
                click.echo("❌ Authentication failed", err=True)
        except Exception as e:
            click.echo(f"❌ Error during authentication test: {e}", err=True)

@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj['config']
    
    click.echo("⚙️  Current Configuration:")
    click.echo(f"   📁 Output directory: {config.output_directory}")
    click.echo(f"   🔑 Credentials file: {config.google_credentials_file}")
    click.echo(f"   🎫 Token file: {config.google_token_file}")
    click.echo(f"   📅 Default days back: {config.days_back}")
    click.echo(f"   🔍 Calendar keywords: {', '.join(config.calendar_keywords)}")
    
    # Check file existence
    click.echo(f"\n📋 File Status:")
    click.echo(f"   Credentials: {'✅' if config.google_credentials_file.exists() else '❌'}")
    click.echo(f"   Token: {'✅' if config.google_token_file.exists() else '❌'}")
    click.echo(f"   Output dir: {'✅' if config.output_directory.exists() else '❌'}")

@cli.command()
@click.argument('meeting_name', required=False)
@click.option('--series-id', help='Compare by series ID instead of meeting name')
@click.option('--weeks', nargs=2, help='Compare specific weeks (YYYY-WW format)')
@click.option('--last', type=int, default=2, help='Compare last N meetings (default: 2)')
@click.option('--summary', is_flag=True, help='Show only summary, not detailed diff')
@click.option('--output', help='Save diff to file')
@click.pass_context
def diff(ctx, meeting_name, series_id, weeks, last, summary, output):
    """Compare meeting notes across different instances."""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    if not meeting_name and not series_id:
        click.echo("❌ Please provide either a meeting name or --series-id", err=True)
        return
    
    try:
        # Initialize components
        tracker = MeetingSeriesTracker(config.output_directory)
        cache = MeetingContentCache(config.output_directory)
        hasher = ContentHasher()
        diff_engine = DiffEngine()
        
        # Find the series
        if series_id:
            target_series_id = series_id
        else:
            # Search for series by meeting name
            all_series = tracker.get_all_series()
            matching_series = []
            
            for sid, series_data in all_series.items():
                series_title = series_data.get('normalized_title', '')
                if meeting_name.lower() in series_title.lower():
                    matching_series.append((sid, series_data))
            
            if not matching_series:
                click.echo(f"❌ No meeting series found matching '{meeting_name}'", err=True)
                return
            elif len(matching_series) > 1:
                click.echo("🔍 Multiple matching series found:")
                for sid, data in matching_series:
                    click.echo(f"   {sid}: {data.get('normalized_title', 'Unknown')}")
                click.echo("Please use --series-id to specify")
                return
            
            target_series_id = matching_series[0][0]
        
        # Get signatures to compare
        if weeks:
            # Compare specific weeks
            click.echo(f"📊 Comparing weeks {weeks[0]} and {weeks[1]}...")
            # TODO: Implement week-based comparison
            click.echo("Week-based comparison not yet implemented")
            return
        else:
            # Get last N meetings
            signatures = cache.get_latest_signatures(target_series_id, limit=last)
            
            if len(signatures) < 2:
                click.echo(f"❌ Not enough meetings to compare (found {len(signatures)})", err=True)
                return
            
            # Compare most recent two
            old_sig = signatures[1]
            new_sig = signatures[0]
        
        # Perform diff
        meeting_diff = diff_engine.compare_meetings(old_sig, new_sig)
        
        # Display results
        if summary:
            click.echo(diff_engine.format_diff_summary(meeting_diff))
        else:
            # Full diff display
            click.echo(diff_engine.format_diff_summary(meeting_diff))
            click.echo("\n📋 Detailed Changes:")
            
            for section_change in meeting_diff.section_changes:
                if section_change.change_type.value == "added":
                    click.echo(f"\n✅ New Section: [{section_change.new_section.header}]")
                    for para in section_change.new_section.paragraphs:
                        click.echo(f"   + {para.preview}")
                elif section_change.change_type.value == "removed":
                    click.echo(f"\n❌ Removed Section: [{section_change.old_section.header}]")
                elif section_change.change_type.value == "modified":
                    click.echo(f"\n🔄 Modified Section: [{section_change.old_section.header}]")
                    for para_change in section_change.paragraph_changes:
                        if para_change.change_type.value == "added":
                            click.echo(f"   + {para_change.new_paragraph.preview}")
                        elif para_change.change_type.value == "removed":
                            click.echo(f"   - {para_change.old_paragraph.preview}")
                        elif para_change.change_type.value == "modified":
                            click.echo(f"   ~ {para_change.old_paragraph.preview}")
                            click.echo(f"     → {para_change.new_paragraph.preview}")
            
            if meeting_diff.moved_paragraphs:
                click.echo("\n↔️  Moved Content:")
                for move in meeting_diff.moved_paragraphs:
                    click.echo(f"   {move.old_section} → {move.new_section}: {move.old_paragraph.preview}")
        
        # Save to file if requested
        if output:
            # TODO: Implement file output
            click.echo(f"Output to file not yet implemented: {output}")
            
    except Exception as e:
        logger.error(f"Error during diff operation: {e}")
        click.echo(f"❌ Error: {e}", err=True)

@cli.command()
@click.argument('meeting_name', required=False)
@click.option('--series-id', help='Show changelog by series ID')
@click.option('--last', type=int, default=4, help='Show last N meetings (default: 4)')
@click.option('--since', help='Show changes since date (YYYY-MM-DD)')
@click.option('--all-series', is_flag=True, help='Show changes for all series')
@click.option('--format', type=click.Choice(['text', 'markdown', 'json']), default='text', help='Output format')
@click.pass_context
def changelog(ctx, meeting_name, series_id, last, since, all_series, format):
    """Show changelog for recurring meetings."""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    if not any([meeting_name, series_id, all_series]):
        click.echo("❌ Please provide meeting name, --series-id, or --all-series", err=True)
        return
    
    try:
        # Initialize components
        tracker = MeetingSeriesTracker(config.output_directory)
        cache = MeetingContentCache(config.output_directory)
        diff_engine = DiffEngine()
        
        # Determine which series to process
        series_to_process = []
        
        if all_series:
            series_to_process = list(tracker.get_all_series().keys())
        elif series_id:
            series_to_process = [series_id]
        else:
            # Find by meeting name
            all_series_data = tracker.get_all_series()
            for sid, series_data in all_series_data.items():
                if meeting_name.lower() in series_data.get('normalized_title', '').lower():
                    series_to_process.append(sid)
        
        if not series_to_process:
            click.echo(f"❌ No meeting series found", err=True)
            return
        
        # Process each series
        for sid in series_to_process:
            series_data = tracker.series_registry.get(sid, {})
            click.echo(f"\n📅 Changelog for: {series_data.get('normalized_title', sid)}")
            click.echo(f"   Series ID: {sid}")
            
            # Get signatures
            if since:
                # TODO: Implement date-based filtering
                signatures = cache.get_latest_signatures(sid, limit=20)
            else:
                signatures = cache.get_latest_signatures(sid, limit=last)
            
            if len(signatures) < 2:
                click.echo("   ℹ️  Not enough meetings for changelog")
                continue
            
            # Show changes between consecutive meetings
            for i in range(len(signatures) - 1):
                old_sig = signatures[i + 1]
                new_sig = signatures[i]
                
                # Extract dates from meeting IDs
                old_date = old_sig.meeting_id.split('_')[-1]
                new_date = new_sig.meeting_id.split('_')[-1]
                
                meeting_diff = diff_engine.compare_meetings(old_sig, new_sig)
                summary = meeting_diff.summary
                
                if format == 'markdown':
                    click.echo(f"\n### {new_date} (from {old_date})")
                    if summary.total_paragraphs_added > 0:
                        click.echo(f"- ✅ Added: {summary.total_paragraphs_added} paragraphs ({summary.total_words_added} words)")
                    if summary.total_paragraphs_removed > 0:
                        click.echo(f"- ❌ Removed: {summary.total_paragraphs_removed} paragraphs ({summary.total_words_removed} words)")
                    if summary.total_paragraphs_modified > 0:
                        click.echo(f"- 🔄 Modified: {summary.total_paragraphs_modified} paragraphs")
                    if summary.total_paragraphs_moved > 0:
                        click.echo(f"- ↔️  Moved: {summary.total_paragraphs_moved} paragraphs")
                    click.echo(f"- 📈 Similarity: {summary.similarity_percentage:.1f}%")
                else:
                    click.echo(f"\n   📝 {new_date} ← {old_date}")
                    changes = []
                    if summary.total_paragraphs_added > 0:
                        changes.append(f"+{summary.total_paragraphs_added}")
                    if summary.total_paragraphs_removed > 0:
                        changes.append(f"-{summary.total_paragraphs_removed}")
                    if summary.total_paragraphs_modified > 0:
                        changes.append(f"~{summary.total_paragraphs_modified}")
                    if summary.total_paragraphs_moved > 0:
                        changes.append(f"↔{summary.total_paragraphs_moved}")
                    
                    if changes:
                        click.echo(f"      Changes: {' '.join(changes)} | Similarity: {summary.similarity_percentage:.1f}%")
                    else:
                        click.echo(f"      No changes detected")
        
    except Exception as e:
        logger.error(f"Error during changelog operation: {e}")
        click.echo(f"❌ Error: {e}", err=True)

if __name__ == '__main__':
    cli()