#!/usr/bin/env python3
"""Meeting Notes Handler CLI - Main entry point."""

import sys
import os
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
@click.option('--force', '-f', is_flag=True, default=False, help='Force re-fetch meetings even if already processed')
@click.option('--gemini-only', '-g', is_flag=True, default=False, help='Only fetch Gemini notes and transcripts, skip other documents')
@click.option('--smart-filter', '-s', is_flag=True, default=False, help='Apply smart content filtering to extract only new content from recurring meetings')
@click.option('--diff-mode', is_flag=True, default=False, help='Only save new content compared to previous meetings')
@click.option('--no-smart-transcript-exclusion', is_flag=True, default=False, help='Disable smart transcript exclusion (keep transcripts even when Gemini notes are present)')
@click.pass_context
def fetch(ctx, days, dry_run, week, accepted, force, gemini_only, smart_filter, diff_mode, no_smart_transcript_exclusion):
    """Fetch meeting notes from Google Calendar and Docs."""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    if week:
        click.echo(f"Week-specific fetching not yet implemented: {week}")
        return
    
    click.echo("🔍 Fetching meeting notes...")
    if dry_run:
        click.echo("📋 DRY RUN - No files will be saved")
    if accepted:
        click.echo("✅ Filtering for accepted meetings only")
    if force:
        click.echo("🔄 FORCE MODE - Will re-fetch already processed meetings")
    if gemini_only:
        click.echo("🤖 GEMINI MODE - Only fetching Gemini notes and transcripts")
    if smart_filter:
        click.echo("🧠 SMART FILTER - Extracting only new content from recurring meetings")
    if diff_mode:
        click.echo("🔍 DIFF MODE - Only saving new content compared to previous meetings")
    if not no_smart_transcript_exclusion:
        click.echo("🎯 SMART TRANSCRIPT EXCLUSION - Excluding transcripts when Gemini notes are present (saves storage)")

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
            force_refetch=force, 
            gemini_only=gemini_only, 
            smart_filtering=smart_filter,
            diff_mode=diff_mode,
            smart_transcript_exclusion=not no_smart_transcript_exclusion
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

@cli.command()
@click.option('--days', '-d', type=int, help='Number of days back to analyze (default: 7)')
@click.option('--week', '-w', help='Specific week to analyze (YYYY-WW format)')
@click.option('--personal', '-p', is_flag=True, help='Focus on personal action items and discussions')
@click.option('--provider', type=click.Choice(['openai', 'anthropic', 'gemini', 'openrouter']), 
              help='LLM provider to use (overrides config)')
@click.option('--model', help='Specific model to use (overrides config)')
@click.option('--output', '-o', help='Save analysis results to file')
@click.option('--format', type=click.Choice(['json', 'markdown']), default='markdown', 
              help='Output format')
@click.option('--min-relevance', type=float, default=0.3, 
              help='Minimum relevance score for personal analysis (0.0-1.0)')
@click.option('--content-filter', type=click.Choice(['gemini-only', 'no-transcripts', 'all']), 
              help='Content filtering mode (overrides config default)')
@click.option('--include-docs', is_flag=True, 
              help='Include embedded documents (when using no-transcripts filter)')
@click.option('--show-token-usage', is_flag=True, 
              help='Show token usage and cost estimates before processing')
@click.pass_context
def analyze(ctx, days, week, personal, provider, model, output, format, min_relevance, 
           content_filter, include_docs, show_token_usage):
    """Analyze meeting notes using LLM to generate insights and summaries."""
    import asyncio
    from .analyzers import create_analyzer, WeeklyAnalyzer, PersonalAnalyzer
    
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    # Determine provider and model
    analysis_provider = provider or config.analysis_provider
    provider_config = config.get_provider_config(analysis_provider).copy()
    
    if model:
        provider_config['model'] = model
    
    # Validate that we have required configuration
    if not provider_config:
        click.echo(f"❌ No configuration found for provider: {analysis_provider}", err=True)
        click.echo("Please check your config.yaml or run 'meeting-notes config-show'")
        sys.exit(1)
    
    # Check for API key
    api_key_env = provider_config.get('api_key_env')
    if api_key_env and not os.getenv(api_key_env):
        click.echo(f"❌ API key not found in environment variable: {api_key_env}", err=True)
        click.echo(f"Please set your {analysis_provider.upper()} API key:")
        click.echo(f"   export {api_key_env}=your_api_key_here")
        sys.exit(1)
    
    # Get user context for personal analysis
    user_context = config.user_context.copy()
    if personal and not user_context.get('user_name'):
        user_name = click.prompt("Enter your name for personal analysis", type=str)
        user_context['user_name'] = user_name
        
        # Ask for aliases
        aliases_input = click.prompt("Enter any aliases or alternate names (comma-separated, optional)", 
                                   default="", show_default=False)
        if aliases_input.strip():
            user_context['user_aliases'] = [alias.strip() for alias in aliases_input.split(',')]
    
    # Determine content filtering settings
    analysis_content_filter = content_filter or config.content_filter
    analysis_include_docs = include_docs or config.include_embedded_docs
    
    # Set default output file if not provided
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if personal:
            if week:
                output = str(config.output_directory / f"{week}_personal_analysis_{timestamp}.json")
            else:
                output = str(config.output_directory / f"personal_analysis_{days or 30}days_{timestamp}.json")
        else:
            if week:
                output = str(config.output_directory / f"{week}_weekly_analysis_{timestamp}.json")
            else:
                output = str(config.output_directory / f"weekly_analysis_{days or 7}days_{timestamp}.json")
    
    click.echo("🧠 Analyzing meeting notes...")
    click.echo(f"   Provider: {analysis_provider}")
    click.echo(f"   Model: {provider_config.get('model', 'default')}")
    click.echo(f"   Content filter: {analysis_content_filter}")
    if analysis_content_filter == 'no-transcripts':
        click.echo(f"   Include docs: {'yes' if analysis_include_docs else 'no'}")
    
    if personal:
        click.echo(f"   Focus: Personal analysis for {user_context.get('user_name', 'Unknown')}")
    else:
        click.echo("   Focus: Weekly summary of important points")
    
    click.echo(f"   Output: {output}")
    
    try:
        # Create LLM analyzer
        llm_analyzer = create_analyzer(analysis_provider, provider_config)
        templates_dir = str(config.templates_directory)
        
        # Show token usage if requested
        if show_token_usage:
            from .analyzers.content_extractor import MeetingContentExtractor
            extractor = MeetingContentExtractor()
            
            # Determine which directory to analyze
            if week:
                analysis_dir = config.output_directory / week
                if not analysis_dir.exists():
                    click.echo(f"❌ Week directory not found: {analysis_dir}", err=True)
                    return
                analysis_path = str(analysis_dir)
            else:
                analysis_path = str(config.output_directory)
            
            click.echo("\n📊 Analyzing token usage...")
            
            # Get content from meetings
            results = extractor.extract_week_content(
                analysis_path, 
                analysis_content_filter, 
                analysis_include_docs
            )
            
            if results:
                total_content = "\n".join([content for _, content in results])
                total_tokens = extractor.count_tokens(total_content)
                
                # Estimate cost (using GPT-4 pricing as example)
                gpt4_pricing = {'input': 0.03, 'output': 0.06}  # per 1K tokens
                estimated_cost = extractor.estimate_cost(total_content, gpt4_pricing)
                
                click.echo(f"   📝 Meetings to analyze: {len(results)}")
                click.echo(f"   🔢 Total tokens: {total_tokens:,}")
                click.echo(f"   💰 Estimated cost (GPT-4): ${estimated_cost:.2f}")
                
                if estimated_cost > config.cost_warning_threshold:
                    click.echo(f"   ⚠️  Cost warning: Analysis may be expensive (>${config.cost_warning_threshold})")
                    if config.require_confirmation and not click.confirm("Continue with analysis?"):
                        click.echo("Analysis cancelled.")
                        return
            else:
                click.echo("   ℹ️  No meetings found to analyze")
                return
        
        async def run_analysis():
            if personal:
                # Personal analysis
                personal_analyzer = PersonalAnalyzer(
                    llm_analyzer, 
                    templates_dir, 
                    content_filter=analysis_content_filter,
                    include_docs=analysis_include_docs
                )
                
                if week:
                    # Analyze specific week
                    week_dir = config.output_directory / week
                    if not week_dir.exists():
                        click.echo(f"❌ Week directory not found: {week_dir}", err=True)
                        return
                    
                    result = await personal_analyzer.analyze_personal_week(
                        week_directory=str(week_dir),
                        user_context=user_context,
                        min_relevance=min_relevance,
                        output_file=output
                    )
                    
                    click.echo(f"\n📊 Personal Analysis Results for {week}:")
                    
                else:
                    # Analyze last N days
                    result = await personal_analyzer.analyze_personal_last_n_days(
                        base_directory=str(config.output_directory),
                        user_context=user_context,
                        days=days or 30,
                        min_relevance=min_relevance,
                        output_file=output
                    )
                    
                    click.echo(f"\n📊 Personal Analysis Results (last {days or 30} days):")
                
                # Display personal results
                click.echo(f"   📈 Meetings analyzed: {result.total_meetings_analyzed}")
                click.echo(f"   🎯 Relevant meetings: {len(result.meetings_with_involvement)}")
                click.echo(f"   ✅ Action items assigned: {len(result.action_items)}")
                click.echo(f"   💬 Discussions involved: {len(result.discussions_involved)}")
                
                if result.action_items:
                    click.echo(f"\n📋 Your Action Items:")
                    for item in result.action_items[:5]:  # Show first 5
                        deadline = f" (due {item.get('deadline', 'TBD')})" if item.get('deadline') else ""
                        priority = f"[{item.get('priority', 'medium').upper()}]"
                        click.echo(f"   {priority} {item.get('task', 'Unknown task')}{deadline}")
                    
                    if len(result.action_items) > 5:
                        click.echo(f"   ... and {len(result.action_items) - 5} more")
                
                if result.meetings_with_involvement:
                    click.echo(f"\n📝 Meetings with your involvement:")
                    for meeting_title in result.meetings_with_involvement[:3]:
                        click.echo(f"   • {meeting_title}")
                    
                    if len(result.meetings_with_involvement) > 3:
                        click.echo(f"   ... and {len(result.meetings_with_involvement) - 3} more")
            
            else:
                # Weekly summary analysis
                weekly_analyzer = WeeklyAnalyzer(
                    llm_analyzer, 
                    templates_dir, 
                    content_filter=analysis_content_filter,
                    include_docs=analysis_include_docs
                )
                
                if week:
                    # Analyze specific week
                    week_dir = config.output_directory / week
                    if not week_dir.exists():
                        click.echo(f"❌ Week directory not found: {week_dir}", err=True)
                        return
                    
                    result = await weekly_analyzer.analyze_week(
                        week_directory=str(week_dir),
                        output_file=output
                    )
                    
                    click.echo(f"\n📊 Weekly Analysis Results for {week}:")
                    
                else:
                    # Analyze last N days
                    result = await weekly_analyzer.analyze_last_n_days(
                        base_directory=str(config.output_directory),
                        days=days or 7,
                        output_file=output
                    )
                    
                    click.echo(f"\n📊 Weekly Analysis Results (last {days or 7} days):")
                
                # Display weekly results
                click.echo(f"   📈 Meetings analyzed: {result.meetings_analyzed}")
                
                # Debug: Show result structure if empty
                if (not result.most_important_decisions and not result.key_themes and 
                    not result.critical_action_items and not result.notable_risks):
                    click.echo(f"\n🔍 Debug: Result object type: {type(result)}")
                    click.echo(f"   Attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
                
                if result.most_important_decisions:
                    click.echo(f"\n🎯 Most Important Decisions:")
                    for i, decision in enumerate(result.most_important_decisions[:5], 1):
                        click.echo(f"   {i}. {decision}")
                    
                    if len(result.most_important_decisions) > 5:
                        click.echo(f"   ... and {len(result.most_important_decisions) - 5} more")
                else:
                    click.echo(f"\n🎯 Most Important Decisions: None found")
                
                if result.key_themes:
                    click.echo(f"\n📋 Key Themes:")
                    for theme in result.key_themes:
                        click.echo(f"   • {theme}")
                else:
                    click.echo(f"\n📋 Key Themes: None found")
                
                if result.critical_action_items:
                    click.echo(f"\n✅ Critical Action Items:")
                    for item in result.critical_action_items[:5]:
                        if isinstance(item, dict):
                            owner = item.get('owner', 'Unknown')
                            priority = f"[{item.get('priority', 'medium').upper()}]"
                            click.echo(f"   {priority} {owner}: {item.get('task', 'Unknown task')}")
                        else:
                            click.echo(f"   • {item}")
                    
                    if len(result.critical_action_items) > 5:
                        click.echo(f"   ... and {len(result.critical_action_items) - 5} more")
                else:
                    click.echo(f"\n✅ Critical Action Items: None found")
                
                if result.notable_risks:
                    click.echo(f"\n⚠️  Notable Risks:")
                    for risk in result.notable_risks:
                        click.echo(f"   • {risk}")
                else:
                    click.echo(f"\n⚠️  Notable Risks: None found")
        
        # Run the async analysis
        asyncio.run(run_analysis())
        
        click.echo(f"\n💾 Analysis saved to: {output}")
        click.echo(f"\n✅ Analysis complete!")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()