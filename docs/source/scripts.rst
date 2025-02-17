========
Run-perf
========

This script does the heavy lifting, usually it should be executed on
a separate machine and drives the execution. You can see the available
options via ``--help``, but let's have a look at some particularly
insteresting ones:

* ``--hosts`` - specifies the set of machines where the tests will be executed
* ``--[guest-]distro`` - specifies the distro version. No introspection is
  performed so unless you are provisioning the system via ``--provisioner``
  make sure it matches.
* ``--paths`` - can be used to specify downstream assets (see
  :any:`downstream-extensions` for details)
* ``--provisioner`` - this one allowes to optionally execute certain actions on
  the target machine(s) before any testing happens. One example is the
  :mod:`runperf.provisioners.Beaker` which allows to provision the system
  via (already installed) `bkr` command.
* ``--profiles`` - profiles/scenarios under which it should execute all tests.
  Some profiles can be tweaked by adding json-like params after a `:` (eg.
  ``'Localhost:{"RUNPERF_TESTS": ["fio"]}'`` to override set of tests).
* POSITIONAL ARGUMENTS - tests to be executed; one can optionally specify
  extra params using json format separated by `:` (eg.
  ``'fio:{"type":"read"}'``).
* ``--metadata`` - metadata to be attached to this build in KEY=VALUE syntax.
  Some tests might use those metadata to perform extra actions like
  `pbench_server_publish=yes` which results in attempt to copy pbench results
  to the specified pbench_server (again via metadata)
* ``--host-setup-script`` resp. ``--worker-setup-script`` - setup script to
  be executed on host resp. on worker to prepare for execution. Some example
  scripts can be found in ``contrib/setup_scripts`` directory. On worker
  we usually assume the profile takes care of the potential reboot, on
  host one can force-reboot via ``--host-setup-script-reboot`` argument.

Followed by a number of arguments to allow tweaking the target machine or
profiles or other aspects of the execution.

During execution run-perf applies a profile, executes all tests and
collects their output in a ``$RESULT/$PROFILE/$TEST/$SERIAL_ID/`` location.
Afterwards it reverts the profile, applies the next one and continues until
it runs all tests under all profiles.

Now let's focus on the available elements:


.. _runperf-hosts:

Hosts
=====

Hosts are the machines to be utilized in testing. Each test can request
one or multiple machines and it is up to the user to provide sufficient
number of hosts.

Run-perf needs to know certain metadata about each host. You can either
store them in your :ref:`downstream-extensions` via :ref:`downstream-assets`
or you can provide them via ``--force-params`` cmdline argument.

Currently the minimum set of params is:

* ``hugepage_kb`` - which hugepage size to use
* ``numa_nodes`` - number of host's numa nodes
* ``host_cpus`` - how many cpus there are on the host
* ``guest_cpus`` - how many cpus we should use for workers
* ``guest_mem_m`` - how much memory we can use for workers. Leaving enough
  free space for the system is important especially when using hugepages
  as otherwise it might fail to obtain enough continuous memory for them.
* ``arch`` - host's architecture

There are some optional arguments like:

* ``disable_smt`` - whether to disable smt on the host before testing

Profiles
========

Are implemented under :mod:`runperf.profiles` and they can accept
additional parameters. See each profile API documentation for details.

By default profiles are named according to their class but one can
tweak the name (and result dir) by using ``"__NAME__": "custom name"``
extra argument.

There is one shared extra parameter available for all profiles,
the `RUNPERF_TESTS`, which allows to override/extend the set of tests
that will be executed on this profile. Similarly to ``--tests`` one
can specify one or multiple tests, extra arguments are passed as
list of 2 items as ``[test_name, extra_params_dict]``. Special ``$@``
test name can be specified to inject all tests specified by ``--tests``.
For example ``--tests Test1 Test2 --profiles First
Second:{"RUNPERF_TESTS": ["Extra1", "$@", ["Extra2", {"key": "value"}]]}``
results in running ``Test1`` and ``Test2`` on profile ``First`` and
``Extra1``, ``Test1``, ``Test2`` and ``Extra2`` only on profile ``Second``
using ``key: value`` arguments to the test ``Extra2``.

To speedup setup for repeated runs you might want to try the
``__KEEP_ASSETS__`` argument, which preserves the created assets (eg.
images, downloaded isos, ...). Note it will not keep the images
used in testing, just the pristine images to-be-copied for testing.

Localhost
---------

Run directly on the bare-metal (useful to detect host-changes)

DefaultLibvirt
--------------

Single VM created by virt-install with the default setting (qcow2, ...).
Various cloud img providers are bundled to fetch the image and prepare
it for usage.

TunedLibvirt
------------

Single VM created from XML that is defined in `runperf/libvirt/$hostname`
directory (see `--path` option to add custom paths) and also contains
host-specific settings like cgroups to move other processes to unused
CPUs, numa pinning, hugepages, ... The purpose is not to be fast, but
to use different features than default ones.

In this profile one can also force-enable or force-disable the
irqbalance service by supplying ``"irqbalance": true`` or
``"irqbalance": false`` extra profile parameter.

Overcommit1_5
-------------

Spawns multiple DefaultLibvirt VMS to occupy 1.5 host's physical CPUs
and execute the tests on all of them.


Tests
=====

Test runners are implemented under :mod:`runperf.tests` and currently consists
of a few `pbench-based <https://distributed-system-analysis.github.io/pbench/pbench-agent.html>`_
tests. These tests accept any extra argument (specified via
'TestName:{"arg": "val"}') on the cmdline and pass it directly to the
pbench-$test command. Below you can find all/most arguments that can be tweaked.

By default tests are named according to their class but one can
tweak the name (and result dir) by using ``"__NAME__": "custom name"``
extra argument.

In case you want to use the number of cpus per worker you can supply
``__PER_WORKER_CPUS__`` value which will be calculated and replaced
with the expected value (eg. with 8 CPUs and 2 workers the value will
be 4).

It's also possible for the pbench-based tests to tweak the ``pbench_tools``
globally via ``--metadata pbench_tools`` or per-test via
``test:{"pbench_tools": ["sar", "iostat:--interval 3"]}``. The tools
are run on all workers as well as on the main host.

.. _test-fio:

Fio
---

`Fio <https://fio.readthedocs.io/en/latest/fio_doc.html>`_ is a customizable
IO intense test. You can tweak following params:

* ``test-types`` - one or more of read,write,rw,randread,randwrite,randrw
  [read,write,rw]
* ``direct`` - 1 = O_DIRECT enabled (default), 0 = O_DIRECT disabled
* ``sync`` - 1 = O_SYNC enabled, 0 = O_SYNC disabled (default)
* ``rate-iops`` - do not exceeed this IOP rate (per job, per client)
* ``runtime`` - runtime in seconds [180]
* ``ramptime`` - time in seconds to warm up test before taking measurements [10]
* ``block-sizes`` - one or more block sizes in KiB
* ``file-size`` - file sizes in MiB (must be bigger than the biggest block size)
* ``targets`` - one or more directories or block devices
* ``job-mode`` - str=[serial|concurrent]  (default is 'concurrent')
* ``ioengine`` - str= any ioengine fio supports (default is )
* ``iodepth`` - Set the iodepth config variable in the fio job file
* ``config`` - name of the test configuration
* ``tool-group``
* ``numjobs`` - number of jobs to run, if not given then fio default of numjobs=1
  will be used
* ``job-file`` - provide the path of a fio job config file
* ``pre-iteration-script`` - use executable script/program to prepare the system
  for test iteration
* ``samples`` - number of samples to use per test iteration [3]
* ``max-stddev`` - the maximum percent stddev allowed to pass
* ``max-failures`` - the maximum number of failures to get below stddev
* ``histogram-interval-sec`` - set the histogram logging interval in seconds
  (default 10)
* ``sysinfo`` - str= comma separated values of sysinfo to be collected
  available: default, none, all, block, libvirt, kernel_config,
  security_mitigations, sos, topology, ara, stockpile, insights

Unless you know what you are doing you should not be using ``clients,
client-file, postprocess-only, run-dir, install`` arguments when
running via Run-perf as it might lead to unpredictable consequences.

Fio-nbd
-------

This is a special case of :ref:`test-fio` test but it is spawning qemu-nbd
export on each worker and tests the speed of the exported device. You can
still tweak various params (like type, ...) but note that the ``targets``,
``numjobs`` and ``job-file`` should be set automatically to suit the
configuration.

Uperf
-----

`Uperf <http://uperf.org/manual.html>`_ is a customizable network IO intense
test. Currently it only tests network between workers and the host.

You can tweak following params:

* ``tool-group``
* ``config`` - name of the test config (e.g. jumbo_frames_and_network_throughput)
* ``test-types`` - stream, maerts, bidirec, and/or rr [stream]
* ``runtime`` - test measurement period in seconds [60]
* ``message-sizes`` - list of message sizes in bytes [1,64,16384]
* ``protocols`` - tcp and/or udp (note it's not advised to use `udp` with `stream`
  type otherwise kernel can "cheat" and dump the packets instead of sending
  them. It's recommended to use `rr` for `udp` [tcp]
* ``instances`` - list of number of uperf instances to run (default is 1,8,64)
* ``server-node`` - An ordered list of server NUMA nodes which should be used for
  CPU binding
* ``client-node`` - An ordered list of client NUMA nodes which should be used for
  CPU binding
* ``samples`` - the number of times each different test is run (to compute average
  & standard deviations) [3]
* ``max-failures`` - the maximum number of failures to get below stddev
* ``max-stddev`` - the maximum percent stddev allowed to pass
* ``start-iteration-num`` - optionally skip the first (n-1) tests
* ``log-response-times`` - record the response time of every single operation
* ``tool-label-pattern``
* ``sysinfo`` - str= comma separated values of sysinfo to be collected
  available: default, none, all, block, libvirt, kernel_config,
  security_mitigations, sos, topology, ara, stockpile, insights

Unless you know what you are doing you should not be using ``clients,
servers, client-file, postprocess-only, run-dir, install`` arguments when
running via Run-perf as it might lead to unpredictable consequences.

Linpack
-------

`Linpack <http://www.netlib.org/linpack/index.html>`_ can be used to measure
floating point computing power. You can change various options, let's
mention at least the basic ones:

* ``threads`` - the number of threads to be used in testing, you can specify
  multiple variants using comma separated list [by default it uses multiple
  values to cover 1 - (worker_cpus * 2). For example on 8-core system
  it will use ``1,4,8,12,16``]
* ``run-samples`` - number of iteration to be executed of each variant [3]
* ``linpack-binary`` - path to installed linpack binary [by default it tries to
  detect ``linpack`` or ``xlinpack_xeon64`` in ``PATH`` or in the usual
  pbench-fio location]
* ``problem-sizes``
* ``leading-dimensions``
* ``alignment-values``
* ``use-omp``
* ``kmp-affinity``
* ``numactl-args``
* ``lininput-header``
* ``lininput-subheader``

Tests can be extended via :mod:`runperf.tests` entry points
(See :any:`downstream-extensions` section)

Build metadata
==============

The ``--metadata`` option is not only a useful tool to store custom metadata
along with the run-perf results but also a way to tweak certain aspects of
the run-perf execution. Metadata are passed to various places and available
to plugins/tests, examples of some usages:

* ``build`` - Short description of this build, mainly used by html results
  (eg.: ``build=${currentBuild.number}`` in Jenkins environment injects the
  current build number)
* ``url`` - URL to the current build execution, mainly used by html results
  (eg.: ``url=${currentBuild.absoluteUrl}`` in Jenkins environment injects the
  link to the current build)
* ``project`` - Name of the current project, mainly used by
  :class:`runperf.tests.PBenchTest` inherited tests to simplify reverse mapping
  of results to run-perf executions (eg.: ``project=perf-ci-nightly``)
* ``machine_url_base`` - Mainly used by html results to add link to details
  about the machine the tests were executed on; one can use `%(machine)s` to
  inject the long machine name
  (eg.: ``machine_url_base=https://beaker.example.org/view/%(machine)s``)
* ``pbench_server`` - sets the ``pbench_web_server`` when installing pbench
  (eg.: ``pbench_server=https://pbench.example.org``)
* ``pbench_server_publish`` - used by tests inherited from
  :class:`runperf.tests.PBenchTest` to push the results to the specified
  ``pbench_server`` via ``pbench-copy-results``.
* ``pbench_copr_repos`` - Allows to override the default copr repos to
  install pbench from (used in :class:`runperf.utils.pbench.Dnf`)

Additional metadata are being collected by run-perf and injected into the
build metadata file. Before the execution it gathers:

* ``distro`` - should represent the target system distro (no detection is
  performed, it's up to the user to specify it correctly or to use
  a provisioner to make sure it's accurate)
* ``guest_distro`` - guest distro that might be used by the profiles to
  provision workers with.
* ``runperf_version`` - runperf version
* ``runperf_cmd`` - actual command that was used to run this build with
  certain (dynamic or secret; eg. distro, password, metadata, ...) arguments
  masked.
* ``machine`` - addresses of all target machines
* ``machine_url`` - when ``machine_url_base`` is set in metadata a link
  to the first target machine is stored here. It's used by the html
  plugin to add a link to the target machine (eg. beaker where one can
  see the hw info)

Additionally on profile revert a profile environment is being collected and
in the end all target system environment is also gathered and injected
into the metadata json file. These can be used to compare the environments
in case of a change.

.. note:: For test environment changes run-perf relies on pbench result
   file format where benchmark params are stored under
   ``results.json:[index]["iteration_data"]["parameters"]["benchmark"][:]``.
   In case your test does not provide these you can use the
   :mod:`runperf.tests` wrappers to inject these. You can inspire by
   :mod:`runperf.tests.BaseTest.inject_metadata` which is used to inject
   our metadata into this file format.

============
Compare-perf
============

Is capable of comparing multiple run-perf pbench-like results in a clear
human as well as machine readable results. It expects the
``$RESULT/$PROFILE/$TEST/$SERIAL_ID/`` format and looks for ``result.json``
file under each of these directories. In case it understands the format
(pbench json result format) it goes through the results and compares them
among the same ``$PROFILE/$TEST/$SERIAL_ID/`` tests and offers various
outputs:

verbose mode
============

By using `-v[v[v]]` one can increase the verbosity which results in a human
readable representation. Sample output::

   DEBUG| Processing ../runperf-results/10
   DEBUG| Processing ../runperf-results/11
   INFO | PASS: TunedLibvirt/uperf/0000:./tcp_stream-1B-1i/throughput/Gb_sec.mean (GOOD raw 1.18%~~5% (0.008984; 0.00909))
   INFO | PASS: TunedLibvirt/uperf/0000:./tcp_stream-1B-1i/throughput/Gb_sec.stddev (GOOD raw 0.12%~~5% (2.944; 2.825))
   INFO | PASS: TunedLibvirt/uperf/0000:./tcp_stream-16384B-1i/throughput/Gb_sec.mean (GOOD raw 0.06%~~5% (3.457; 3.459))
   ERROR| FAIL: TunedLibvirt/uperf/0000:./udp_stream-16384B-1i/throughput/Gb_sec.mean (SMALL raw -10.86%<-5% (16.95; 15.11))
   ...
   Per-result-id averages:
   result_id                                                  | min   1st   med   3rd  max  a-    a+  | stdmin std1st stdmed std3rd stdmax astd- astd+
   DefaultLibvirt/uperf/0000:./udp_stream-*/throughput/Gb_sec | -5.9  -2.2  -0.5  0.5  3.6  -1.4  0.5 | -1.7   -0.5   0.2    0.6    1.7    -0.4  0.5
   TunedLibvirt/uperf/0000:./udp_stream-*/throughput/Gb_sec   | -10.9 -1.7  -1.4  -0.5 0.8  -1.9  0.1 | -0.4   -0.1   0.0    0.4    1.2    -0.1  0.3
   TunedLibvirt/fio/0000:./read-*/throughput/iops_sec         | -6.4  -5.0  -3.7  2.5  8.6  -3.3  2.9 | -0.9   -0.5   -0.1   0.4    0.9    -0.3  0.3
   TunedLibvirt/fio/0000:./write-*/throughput/iops_sec        | -21.4 -11.1 -0.9  -0.5 -0.2 -7.5  0.0 | -1.1   -0.4   0.3    3.5    6.8    -0.4  2.3
   DefaultLibvirt/fio/0000:./rw-*/throughput/iops_sec         | -2.2  -1.4  -0.7  -0.0 0.6  -0.9  0.2 | -1.2   -1.1   -0.9   -0.7   -0.5   -0.9  0.0
   TunedLibvirt/fio/0000:./rw-*/throughput/iops_sec           | -2.7  -0.0  2.7   6.6  10.5 -0.9  4.4 | -3.3   -3.1   -2.9   -0.9   1.1    -2.1  0.4
   TunedLibvirt/fio/0000:./randrw-*/throughput/iops_sec       | -2.2  -0.4  1.3   1.8  2.2  -0.7  1.2 | -1.7   3.1    8.0    14.7   21.4   -0.6  9.8
   TunedLibvirt/uperf/0000:./tcp_stream-*/throughput/Gb_sec   | -6.5  -0.1  0.4   1.4  2.1  -0.6  0.8 | -0.8   -0.4   -0.1   0.1    3.0    -0.2  0.4
   DefaultLibvirt/fio/0000:./read-*/throughput/iops_sec       | 1.3   2.8   4.4   6.6  8.8  0.0   4.8 | -3.2   -1.6   0.0    0.1    0.1    -1.1  0.1
   DefaultLibvirt/fio/0000:./randrw-*/throughput/iops_sec     | -0.0  1.4   2.8   3.3  3.9  -0.0  2.2 | -0.1   -0.1   -0.0   0.0    0.1    -0.0  0.0
   DefaultLibvirt/fio/0000:./randwrite-*/throughput/iops_sec  | -7.3  -3.4  0.4   0.6  0.7  -2.4  0.4 | -15.1  -7.2   0.7    0.7    0.7    -5.0  0.5
   TunedLibvirt/fio/0000:./randwrite-*/throughput/iops_sec    | -33.4 -27.8 -22.2 -7.9 6.4  -18.5 2.1 | -18.3  -7.0   4.3    7.1    9.8    -6.1  4.7
   TunedLibvirt/fio/0000:./randread-*/throughput/iops_sec     | -9.2  -7.5  -5.8  -2.8 0.2  -5.0  0.1 | -3.0   -3.0   -3.0   -1.5   -0.1   -2.0  0.0
   DefaultLibvirt/fio/0000:./randread-*/throughput/iops_sec   | -1.7  -0.3  1.2   2.5  3.8  -0.6  1.7 | -2.9   -1.3   0.3    0.8    1.2    -1.0  0.5
   DefaultLibvirt/uperf/0000:./tcp_stream-*/throughput/Gb_sec | -3.1  -1.7  -0.2  0.4  1.5  -0.8  0.3 | -3.4   -0.8   -0.2   0.4    2.3    -0.6  0.4
   DefaultLibvirt/fio/0000:./write-*/throughput/iops_sec      | -5.9  -4.7  -3.5  -2.5 -1.5 -3.6  0.0 | -0.9   -0.9   -0.9   0.9    2.7    -0.6  0.9


   INFO | 

   Per-result-id averages:
   result_id                             | min   1st  med  3rd max  a-   a+  | stdmin std1st stdmed std3rd stdmax astd- astd+
   DefaultLibvirt/uperf/*:./*-*/*/Gb_sec | -5.9  -2.0 -0.4 0.4 3.6  -1.1 0.4 | -3.4   -0.7   -0.1   0.6    2.3    -0.5  0.4
   TunedLibvirt/fio/*:./*-*/*/iops_sec   | -33.4 -6.2 -1.5 2.0 10.5 -6.0 1.8 | -18.3  -2.6   -0.1   3.5    21.4   -1.9  2.9
   DefaultLibvirt/fio/*:./*-*/*/iops_sec | -7.3  -1.6 0.5  2.4 8.8  -1.3 1.5 | -15.1  -0.9   -0.1   0.3    2.7    -1.4  0.3
   TunedLibvirt/uperf/*:./*-*/*/Gb_sec   | -10.9 -1.4 -0.4 0.8 2.1  -1.3 0.4 | -0.8   -0.2   -0.0   0.2    3.0    -0.2  0.4


   INFO | 

   Per-result-id averages:
   result_id                    | min   1st  med  3rd max  a-   a+  | stdmin std1st stdmed std3rd stdmax astd- astd+
   TunedLibvirt/*/*:./*-*/*/*   | -33.4 -2.2 -0.5 0.8 10.5 -3.3 1.0 | -18.3  -0.5   -0.0   1.0    21.4   -0.9  1.5
   DefaultLibvirt/*/*:./*-*/*/* | -7.3  -1.9 -0.2 1.0 8.8  -1.2 0.9 | -15.1  -0.9   -0.1   0.6    2.7    -0.9  0.4


   INFO | 

                count med  min   max  sum    avg
   Total        168   -0.1 -33.4 21.4 -106.6 -0.6
   Gains        8     8.7  6.4   21.4 80.3   10.0
   Minor gains  9     3.6  2.7   4.4  31.2   3.5
   Equals       125   -0.0 -2.2  2.3  -9.1   -0.1
   Minor losses 13    -3.1 -3.7  -2.7 -40.8  -3.1
   Losses       13    -9.2 -33.4 -5.8 -168.1 -12.9
   Errors       0

html results
============

Can be enabled by ``--html $PATH`` and is especially useful for multiple
results comparison. It always compares the source build to all reference
builds and the destination build and generates a standalone html page with
comparison, which is useful for email attachments.

Sample output of multiple results can be seen
`here <_static/html_result.html>`_ and was generated using (partial) results
stored in ``selftests/.assets/results`` in the run-perf sources using a model
located in ``selftests/.assets/results/1_base/linear_model.json`` using
first five results from that directory.

let's have a look at the available sections:

Overall information table
-------------------------

Contains useful information about the ways each build was executed and what
is the baseline. Some entries are replaced by A,B,C... to avoid unnecessary
long lines, but you can always get the real value on mouse over but all A-s
within one line are of the same value.

 * `Build` - link to the build that was used to generate the results
   (build_prefix is suffixed to the build number)
 * `Machine` - on which machine it was executed
 * `Distro` - which host distribution was used
 * `Guest distro` - which distribution was used on guest (DISTRO means the same
   as on host)
 * `Runperf version` - runperf commit used to execute the job (important only
   in case profiles/tests are changed - not frequently...)
 * `Runperf command` - can indicate how the build was different (some values
   are replaced with values representing the option, eg. passwords or file
   contents)
 * `World env` - signals what changed on the main system between different
   builds. On hover it shows ``diff`` of the environment compare to the source
   build and on click (anywhere on the letter or in the tooltip) it copies
   the json value with the full environment to your clipboard (use ``ctrl+v``
   to retrieve it).
 * `* env` - the same as ``World env`` only for each profile that was used in
   this execution. On top of the usual it can contain things like libvirt xml.
 * `Tests env` - Lists tests with different params from the src build. In this
   overview you can only get the list of tests to see the individual params
   as well as actual differences you need to hover/click on the wrench icon
   next to each test (see `Table of failures`_ below)
 * `Failures` - number of failures
 * `Group failures` - number of aggregated failures (eg. when all fio tests
   break the group failures rate)
 * `Non-primary failures` - number of non-primary failures
 * `Total checks` - number of tests
 * `Build score` - somehow represents how different the build is from the
   baseline (doesn't mean slower or faster, only how different). It is also
   used to colour the columns to highlight the most distant builds.

Table of failures
-----------------

It's a table of all primary results, can be dynamically filtered and by
default shows only tests that failed in any of the builds. You can use the
buttons on top to change the filters in order to better understand the
conditions.

The values in the table represent the gain/loss. The number is a weight
average of all applied models and on hover you can get more details.
Based on the used models you can get one or multiple:

* ``raw`` - raw difference from the source job
* ``avg`` - average value of this and all reference builds
* ``model*`` - percentage difference using the model (provided by linear
  regression model)
* ``mraw*`` - raw difference from average source value from the builds
  included in model (provided by linear regression model)

followed by multiple number in brackets. First value are slash (``/``)
separated source values collected from models and after semicolon (``;``)
this build's raw value.

In case the test parameters are different from the source job a `🔧` character.
On hover it displays the diff of src and this test params. On click (on the
character as well as anywhere in the tooltip) it pastes the raw params to
system clipboard (use ``ctrl+v`` to retrieve it). The source result params can
be retrieved via the icon next to the test name. Note that group results don't
contain the test params, then the `🔧` icon is not displayed.

.. tip:: I find this table the best source of the information.

Details
-------

This section is hidden by default as it's mainly superseded by
table-of-failures, but some might prefer it. It only compares the source
(or model) build to the destination build, but also includes some facts
about number of failures in reference builds.

Charts
------

Charts are not generated by default but can be enabled via
``--html-with-charts``. Especially when multiple profiles as well as tests
are executed they can be quite useful, but they add quite a big amount of
javascript code, which is why they are not enabled by default.

First section is "Overall mean" and it includes all (primary) tests.
Left chart shows number of results per given category, the right chart
shows statistic data about each category (minimum, 1st quantile, median,
3rd quantile and maximum). Scrolling down you'll see the same charts that
include results of only some of the tests, for example focussing only on
results executed under TunedLibvirt profile, or using tcp_stream uperf
test.


============
Analyze-perf
============

Is used to process multiple results.

CSV
===

Unlike in `compare-perf`_ the ``--csv`` CSV output is quite useful here as it
creates a table of all ``$PROFILE/$TEST/$SERIAL_ID/`` and adds the ``$RESULT``
values into collumns.

Linear regression model
=======================

Can be generated with ``--stddev-linear-regression`` and
``--linear-regresion`` arguments and they both map the jittery values of
the analyzed builds to the ``--tolerance``. The difference is that the
`Stddev linear regression` model uses 3x the standard deviation of the
samples and usually is less prone to outliers, while the
``Linear regression`` model uses min/max values of the builds so it
requires carefully chosen model builds as any outlier might spoil the
model.

The way it works is that it goes through the individual
``$PROFILE/$TEST/$SERIAL_ID/`` values and calculates coefficients of linear
equation to normalize the values to range given by ``--tolerance``. It can
result in lenient or stricter measures applied to individual results based
on the usual spread of results.


=========
Diff-perf
=========

Is simlar to compare-perf but instead of checking for errors it looks to
the individual values and counts which result got the closest value.
Primary usage would be a bisection where you have a good result,
bad result and you are trying to find-out whether a single result is
closer to the good one or a bad one, but it allows to compare to any
amount of results.

A helper for bisection can be found in ``contrib/bisect.sh`` and
a specific example for upstream qemu bisection in
``contrib/upstream_qemu_bisect.sh``. You can also check-out
the :ref:`jenkins` chapter for a jenkins pipeline
using it.


==============
Strip-run-perf
==============

This tool can be used to obtain stripped results that only contain the
bits used by run-perf tools (compare-perf, ...). It can reduce the results
significantly (MB->KB) but you are going to lose all of the extra
information essential to debug issues. The primary focus is to keep
run-perf data while storing the detailed information elsewhere.
