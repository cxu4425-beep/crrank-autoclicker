package com.crrank.autoharvest;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** 精簡 QR Code 產生器：位元組模式、錯誤修正等級 M、版本 1–10。 */
public final class QrGen {
    private static final int[] ECC_PER_BLOCK = {-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26};
    private static final int[] NUM_BLOCKS = {-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5};

    private final int size;
    private final boolean[][] mod;
    private final boolean[][] fn;

    private QrGen(int ver) {
        size = ver * 4 + 17;
        mod = new boolean[size][size];
        fn = new boolean[size][size];
    }

    public static boolean[][] encode(String text) {
        return encode(text, 2);
    }

    public static boolean[][] encode(String text, int mask) {
        byte[] data = text.getBytes(StandardCharsets.UTF_8);
        int ver = 1;
        for (; ver <= 10; ver++) {
            int cap = numDataCodewords(ver) * 8;
            int need = 4 + (ver < 10 ? 8 : 16) + data.length * 8;
            if (need <= cap) break;
        }
        if (ver > 10) throw new IllegalArgumentException("text too long");
        int cap = numDataCodewords(ver) * 8;
        List<Integer> bits = new ArrayList<>();
        appendBits(bits, 4, 4);
        appendBits(bits, data.length, ver < 10 ? 8 : 16);
        for (byte b : data) appendBits(bits, b & 0xFF, 8);
        appendBits(bits, 0, Math.min(4, cap - bits.size()));
        appendBits(bits, 0, (8 - bits.size() % 8) % 8);
        for (int pad = 0xEC; bits.size() < cap; pad ^= 0xEC ^ 0x11) appendBits(bits, pad, 8);
        byte[] cw = new byte[bits.size() / 8];
        for (int i = 0; i < bits.size(); i++) cw[i >>> 3] |= bits.get(i) << (7 - (i & 7));

        QrGen q = new QrGen(ver);
        q.drawFunctionPatterns(ver);
        q.drawCodewords(q.addEccAndInterleave(ver, cw));
        q.applyMask(mask);
        q.drawFormatBits(mask);
        return q.mod;
    }

    private static void appendBits(List<Integer> bb, int val, int len) {
        for (int i = len - 1; i >= 0; i--) bb.add((val >>> i) & 1);
    }

    private static int numRawDataModules(int ver) {
        int r = (16 * ver + 128) * ver + 64;
        if (ver >= 2) {
            int na = ver / 7 + 2;
            r -= (25 * na - 10) * na - 55;
            if (ver >= 7) r -= 36;
        }
        return r;
    }

    private static int numDataCodewords(int ver) {
        return numRawDataModules(ver) / 8 - ECC_PER_BLOCK[ver] * NUM_BLOCKS[ver];
    }

    private void set(int x, int y, boolean dark) {
        mod[y][x] = dark;
        fn[y][x] = true;
    }

    private void drawFunctionPatterns(int ver) {
        for (int i = 0; i < size; i++) {
            set(6, i, i % 2 == 0);
            set(i, 6, i % 2 == 0);
        }
        drawFinder(3, 3);
        drawFinder(size - 4, 3);
        drawFinder(3, size - 4);
        int[] al = alignmentPositions(ver);
        int n = al.length;
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (!(i == 0 && j == 0 || i == 0 && j == n - 1 || i == n - 1 && j == 0))
                    for (int dy = -2; dy <= 2; dy++)
                        for (int dx = -2; dx <= 2; dx++)
                            set(al[i] + dx, al[j] + dy, Math.max(Math.abs(dx), Math.abs(dy)) != 1);
        drawFormatBits(0);
        if (ver >= 7) {
            int rem = ver;
            for (int i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
            int bits = ver << 12 | rem;
            for (int i = 0; i < 18; i++) {
                boolean b = ((bits >>> i) & 1) != 0;
                int a = size - 11 + i % 3, c = i / 3;
                set(a, c, b);
                set(c, a, b);
            }
        }
    }

    private void drawFinder(int x, int y) {
        for (int dy = -4; dy <= 4; dy++)
            for (int dx = -4; dx <= 4; dx++) {
                int d = Math.max(Math.abs(dx), Math.abs(dy));
                int xx = x + dx, yy = y + dy;
                if (xx >= 0 && xx < size && yy >= 0 && yy < size) set(xx, yy, d != 2 && d != 4);
            }
    }

    private int[] alignmentPositions(int ver) {
        if (ver == 1) return new int[0];
        int na = ver / 7 + 2;
        int step = (ver * 8 + na * 3 + 5) / (na * 4 - 4) * 2;
        int[] r = new int[na];
        r[0] = 6;
        for (int i = na - 1, pos = size - 7; i >= 1; i--, pos -= step) r[i] = pos;
        return r;
    }

    private void drawFormatBits(int mask) {
        int data = (0 << 3) | mask; // M = 00
        int rem = data;
        for (int i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
        int bits = (data << 10 | rem) ^ 0x5412;
        for (int i = 0; i <= 5; i++) set(8, i, bit(bits, i));
        set(8, 7, bit(bits, 6));
        set(8, 8, bit(bits, 7));
        set(7, 8, bit(bits, 8));
        for (int i = 9; i < 15; i++) set(14 - i, 8, bit(bits, i));
        for (int i = 0; i < 8; i++) set(size - 1 - i, 8, bit(bits, i));
        for (int i = 8; i < 15; i++) set(8, size - 15 + i, bit(bits, i));
        set(8, size - 8, true);
    }

    private static boolean bit(int x, int i) {
        return ((x >>> i) & 1) != 0;
    }

    private byte[] addEccAndInterleave(int ver, byte[] data) {
        int nb = NUM_BLOCKS[ver], ecl = ECC_PER_BLOCK[ver];
        int raw = numRawDataModules(ver) / 8;
        int nShort = nb - raw % nb;
        int shortLen = raw / nb;
        byte[] div = rsDivisor(ecl);
        byte[][] blocks = new byte[nb][];
        for (int i = 0, k = 0; i < nb; i++) {
            int dl = shortLen - ecl + (i < nShort ? 0 : 1);
            byte[] dat = new byte[dl];
            System.arraycopy(data, k, dat, 0, dl);
            k += dl;
            byte[] ecc = rsRemainder(dat, div);
            byte[] blk = new byte[shortLen + 1];
            System.arraycopy(dat, 0, blk, 0, dl);
            System.arraycopy(ecc, 0, blk, blk.length - ecl, ecl);
            blocks[i] = blk;
        }
        byte[] res = new byte[raw];
        int idx = 0;
        for (int i = 0; i < blocks[0].length; i++)
            for (int j = 0; j < nb; j++)
                if (i != shortLen - ecl || j >= nShort) res[idx++] = blocks[j][i];
        return res;
    }

    private static byte[] rsDivisor(int deg) {
        byte[] r = new byte[deg];
        r[deg - 1] = 1;
        int root = 1;
        for (int i = 0; i < deg; i++) {
            for (int j = 0; j < deg; j++) {
                r[j] = (byte) mul(r[j] & 0xFF, root);
                if (j + 1 < deg) r[j] ^= r[j + 1];
            }
            root = mul(root, 0x02);
        }
        return r;
    }

    private static byte[] rsRemainder(byte[] data, byte[] div) {
        byte[] r = new byte[div.length];
        for (byte b : data) {
            int f = (b ^ r[0]) & 0xFF;
            System.arraycopy(r, 1, r, 0, r.length - 1);
            r[r.length - 1] = 0;
            for (int i = 0; i < r.length; i++) r[i] ^= mul(div[i] & 0xFF, f);
        }
        return r;
    }

    private static int mul(int x, int y) {
        int z = 0;
        for (int i = 7; i >= 0; i--) {
            z = (z << 1) ^ ((z >>> 7) * 0x11D);
            z ^= ((y >>> i) & 1) * x;
        }
        return z;
    }

    private void drawCodewords(byte[] data) {
        int i = 0;
        for (int right = size - 1; right >= 1; right -= 2) {
            if (right == 6) right = 5;
            for (int vert = 0; vert < size; vert++)
                for (int j = 0; j < 2; j++) {
                    int x = right - j;
                    boolean up = ((right + 1) & 2) == 0;
                    int y = up ? size - 1 - vert : vert;
                    if (!fn[y][x] && i < data.length * 8) {
                        mod[y][x] = bit(data[i >>> 3], 7 - (i & 7));
                        i++;
                    }
                }
        }
    }

    private void applyMask(int m) {
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++) {
                boolean inv;
                switch (m) {
                    case 0: inv = (x + y) % 2 == 0; break;
                    case 1: inv = y % 2 == 0; break;
                    case 2: inv = x % 3 == 0; break;
                    case 3: inv = (x + y) % 3 == 0; break;
                    case 4: inv = (x / 3 + y / 2) % 2 == 0; break;
                    case 5: inv = x * y % 2 + x * y % 3 == 0; break;
                    case 6: inv = (x * y % 2 + x * y % 3) % 2 == 0; break;
                    default: inv = ((x + y) % 2 + x * y % 3) % 2 == 0; break;
                }
                if (!fn[y][x] && inv) mod[y][x] = !mod[y][x];
            }
    }

    /** 測試用：輸出 0/1 矩陣 */
    public static void main(String[] a) {
        boolean[][] m = encode(a[0], Integer.parseInt(a[1]));
        StringBuilder sb = new StringBuilder();
        for (boolean[] row : m) {
            for (boolean b : row) sb.append(b ? '1' : '0');
            sb.append('\n');
        }
        System.out.print(sb);
    }
}
