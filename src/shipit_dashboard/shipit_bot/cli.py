import click
import os.path
import tempfile
from shipit_bot.sync import BotRemote


DEFAULT_CACHE = os.path.join(tempfile.gettempdir(), 'shipit_bot_cache')


@click.command()
@click.option('--secrets', required=True, help='Taskcluster Secrets path')
@click.option('--client-id', help='Taskcluster Client ID')
@click.option('--client-token', help='Taskcluster Client token')
@click.option('--cache-root', default=DEFAULT_CACHE, help='Cache for repository clones.')  # noqa
def main(secrets, client_id, client_token, cache_root):
    """
    Run bot to sync bug & analysis on a remote server
    """
    bot = BotRemote(secrets, client_id, client_token)
    bot.use_cache(cache_root)
    bot.run()


if __name__ == '__main__':
    main()
