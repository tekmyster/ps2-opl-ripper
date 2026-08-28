from ps2ripper.opl.layout import OPL_DIRECTORIES
from ps2ripper.storage.exfat import (
    independently_check_boot_regions,
    initialize_image,
    recommended_exfat_cluster_size,
    reopen_image_directories,
)


def test_default_cluster_sizes():
    assert recommended_exfat_cluster_size(256 * 1024**2) == 4 * 1024
    assert recommended_exfat_cluster_size(257 * 1024**2) == 32 * 1024
    assert recommended_exfat_cluster_size(33 * 1024**3) == 128 * 1024


def test_mbr_exfat_image_and_opl_directories(tmp_path):
    image = tmp_path / "opl.img"
    result = initialize_image(image, 256 * 1024**2)
    independently_check_boot_regions(image, result)
    assert set(reopen_image_directories(image)) == set(OPL_DIRECTORIES)
    assert result.partition_offset == 1024 * 1024
    assert result.cluster_size == 4 * 1024
