#!/bin/env python3
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat Inc. 2020
# Author: Lukas Doktor <ldoktor@redhat.com>
"""
Tests for the profiles handling
"""

# pylint: disable=W0212

import argparse
import os
import shutil
from unittest import mock

from runperf import profiles
from runperf.machine import Host, ShellSession
from runperf.profiles import Localhost, DefaultLibvirt

from . import Selftest


class TunedLibvirt(profiles.TunedLibvirt):

    """Mocked TunedLibvirt profile"""

    selftest_root = None

    def _get_image(self, session, setup_script):
        del session, setup_script
        return os.path.join(self.selftest_root, "__test_image__.qcow2")

    def _start_vms(self):
        # Report localhost as the worker
        self.vms = [self.host]
        return self.vms

    def _read_file(self, path, default=-1):
        if path == "/proc/cmdline":
            return ""
        return profiles.TunedLibvirt._read_file(self, path, default=default)


class ProfileUnitTests(Selftest):

    """Various profile unit tests"""

    def test_file_handling(self):
        asset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  ".assets")
        args = argparse.Namespace(guest_distro="__test_distro__",
                                  default_passwords="foo", paths=[asset_path],
                                  force_params=[])
        with mock.patch("runperf.profiles.CONFIG_DIR", self.tmpdir):
            host = Host(mock.Mock(), "selftest", "addr", "__test_distro__",
                        args)
            host.get_session = lambda *args, **kwargs: ShellSession("sh")
            profile = Localhost(host, self.tmpdir)
            # basic handling
            self.assertEqual(-1, profile._get("foo"))
            obj = object()
            self.assertEqual(obj, profile._get("foo", obj))
            profile._set("foo", "bar", True)
            self.assertEqual("bar", profile._get("foo"))
            self.assertRaises(ValueError, profile._set, "foo", "baz", True)
            profile._append("foo", "baz")
            self.assertRaises(ValueError, profile._append, "foo", "a\nb")
            self.assertEqual(["bar", "baz"], profile._get("foo").splitlines())
            # get_info
            info = list(profile.get_info().keys())
            if "rpm" in info:  # rpm is only there when rpm command available
                info.remove("rpm")
            self.assertEqual(["general", "kernel", "mitigations", "params"],
                             info)
            # revert not applied profile
            profile.revert()
            # revert different profile
            profile._set("set_profile", "foo")
            self.assertRaises(NotImplementedError, profile.revert)
            # apply the profile
            profile._remove("set_profile")
            profile.apply(None)
            # paths to be removed
            profile._set("a", "a")
            profile._set("b", "b")
            patha = profile._persistent_storage_path("a")
            pathb = profile._persistent_storage_path("b")
            profile._path_to_be_removed(patha)
            profile._path_to_be_removed(pathb)
            self.assertTrue(os.path.exists(patha))
            self.assertTrue(os.path.exists(pathb))
            profile.revert()
            self.assertFalse(os.path.exists(patha))
            self.assertFalse(os.path.exists(pathb))
            # double revert
            profile.revert()
            # delete active profile
            profile = Localhost(host, self.tmpdir)
            session = profile.session
            del profile
            self.assertTrue(session.closed)

    def test_libvirt_image_up_to_date(self):
        asset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  ".assets")
        args = argparse.Namespace(guest_distro="__test_distro__",
                                  default_passwords="foo", paths=[asset_path],
                                  force_params=[])
        with mock.patch("runperf.profiles.CONFIG_DIR", self.tmpdir):
            host = Host(mock.Mock(), "selftest", "addr", "__test_distro__",
                        args)
            host.get_session = lambda *args, **kwargs: ShellSession("sh")
            profile = DefaultLibvirt(host, self.tmpdir)
            pubkey = os.path.join(self.tmpdir, "pubkey")
            image = os.path.join(self.tmpdir, "image")
            setup_script = "foo"
            setup_script_path = os.path.join(self.tmpdir, "setup_script")
            # missing image
            self.assertEqual("does not exists", profile._image_up_to_date(
                profile.session, pubkey, image, setup_script,
                setup_script_path))
            profile.shared_pub_key = "aaa"
            with open(image, 'w'):
                pass
            with open(pubkey, 'w') as fd_pubkey:
                fd_pubkey.write("bbb\n")
            self.assertEqual("has wrong public key", profile._image_up_to_date(
                profile.session, pubkey, image, setup_script,
                setup_script_path))
            with open(pubkey, 'w') as fd_pubkey:
                fd_pubkey.write("aaa\n")
            out = profile._image_up_to_date(profile.session, pubkey, image,
                                            setup_script, setup_script_path)
            self.assertEqual("not created with setup script", out)
            with open(setup_script_path, 'w') as fd_setup_script:
                fd_setup_script.write("bar\n")
            out = profile._image_up_to_date(profile.session, pubkey, image,
                                            setup_script, setup_script_path)
            self.assertEqual("created with a different setup script", out)
            out = profile._image_up_to_date(profile.session, pubkey, image,
                                            None, setup_script_path)
            self.assertEqual("created with setup script", out)
            with open(setup_script_path, 'w') as fd_setup_script:
                fd_setup_script.write("foo\n")
            out = profile._image_up_to_date(profile.session, pubkey, image,
                                            setup_script, setup_script_path)
            self.assertEqual(None, out)
            os.unlink(setup_script_path)
            out = profile._image_up_to_date(profile.session, pubkey, image,
                                            None, setup_script_path)
            self.assertEqual(None, out)


class RunPerfTest(Selftest):

    """Full runperf workflow tests"""

    def test_tuned_libvirt(self):
        # runperf dir must end with '/'
        runperf_dir = os.path.join(self.tmpdir, "runperf") + os.path.sep
        os.makedirs(runperf_dir)
        asset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  ".assets")
        args = argparse.Namespace(guest_distro="__test_distro__",
                                  default_passwords="foo", paths=[asset_path],
                                  force_params=[])
        # For "tuned-adm" we need to return "something : virtual-host"
        # session = mock.Mock(**{'cmd.return_value': "something : virtual-host"})
        session = mock.Mock()
        host = Host(mock.Mock(), "selftest", "addr", "__test_distro__",
                    args)
        host.get_session = lambda *args, **kwargs: session
        host.copy_from = shutil.copy
        with mock.patch("runperf.profiles.CONFIG_DIR", runperf_dir):
            profile = TunedLibvirt(host, [asset_path])
            profile.selftest_root = runperf_dir
            # Persistent apply, should ask for reboot
            session.cmd.return_value = "some:value"
            session.cmd_status.return_value = 1
            session.cmd_output.return_value = "some:value"
            self.assertEqual(True, profile.apply(None))
            self.check_calls(session.mock_calls,
                             ["set_profile",
                              "persistent_profile_expected << ", "rc_local",
                              "tuned-adm profile virtual-host",
                              "persistent_setup/grub_args <<"])
            session.reset_mock()
            # Non-persistent apply, should report (mocked) VMs
            session.cmd_output.return_value = "rc_local"
            session.cmd_status.side_effect = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual([host], profile.apply(None))
            self.assertIn("persistent_setup_expected", str(session.mock_calls))
            self.assertIn("persistent_setup_finished", str(session.mock_calls))
            session.cmd_status.side_effect = None
            session.reset_mock()
            # Running apply when profile already applied should fail
            session.cmd_status.return_value = 0
            session.cmd_output.return_value = "some:value"
            self.assertRaises(RuntimeError, profile.apply, None)
            session.reset_mock()
            # get_info should combine default get info and persistent get_info
            info = list(profile.get_info().keys())
            if "rpm" in info:  # rpm is only there when rpm command available
                info.remove("rpm")
                info.remove("guest0_rpm")
            self.assertEqual(['general', 'kernel', 'mitigations', 'params',
                              'persistent', 'guest0_general', 'guest0_kernel',
                              'guest0_mitigations', 'guest0_params'], info)
            # Revert the profile
            session.cmd_status.return_value = 0
            session.cmd_output.return_value = "TunedLibvirt"
            profile.revert()
            for cmd in ("set_profile", "grub_args", "tuned_adm_profile",
                        "rc_local", "persistent_setup_finished",
                        "persistent_setup_expected"):
                self.assertIn(cmd, str(session.mock_calls))
