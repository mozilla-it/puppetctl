'''
    Basic entry point for the script to use.
'''
import sys
from puppetctl import PuppetctlCLIHandler


def main():
    ''' puppetctl cli entry point '''
    cli_handler = PuppetctlCLIHandler()
    cli_handler.main(sys.argv)

if __name__ == '__main__':
    main()  # pragma: no cover
