import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.util.Timer;
import java.util.TimerTask;

public class AutoKeyDrueckertest2 {

    private static boolean running = false;
    private static Timer timer;

    public static void main(String[] args) {
        SwingUtilities.invokeLater(AutoKeyDrueckertest2::createUI);
    }

    private static void createUI() {
        JFrame frame = new JFrame("AutoKeyDrueckertest2");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(400, 400);
        frame.setLocationRelativeTo(null);

        GradientRepaintablePanel gradientPanel = new GradientRepaintablePanel();
        gradientPanel.setLayout(new GridBagLayout());
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(6, 6, 6, 6);
        gbc.fill = GridBagConstraints.HORIZONTAL;

        // UI-Komponenten
        JTextField keyField = new JTextField("R", 10);
        JTextField delayField = new JTextField("100", 10);
        JTextField repeatField = new JTextField("0", 10);
        JCheckBox shiftBox = new JCheckBox("Shift");
        JCheckBox ctrlAltBox = new JCheckBox("Strg + Alt");
        JCheckBox alwaysOnTop = new JCheckBox("Always on Top", true);
        JCheckBox darkModeBox = new JCheckBox("Dark Mode");
        JButton startButton = new JButton("Start");

        // Labels separat für Dark Mode Zugriff
        JLabel labelKey = new JLabel("Taste:");
        JLabel labelDelay = new JLabel("Wiederholrate (ms):");
        JLabel labelRepeat = new JLabel("Wiederholungen (0 = inf):");

        // Alle umzufärbenden Komponenten
        Component[] darkComponents = {
            keyField, delayField, repeatField,
            shiftBox, ctrlAltBox, alwaysOnTop, darkModeBox, startButton,
            labelKey, labelDelay, labelRepeat
        };

        // Layout Aufbau
        gbc.gridx = 0; gbc.gridy = 0;
        gradientPanel.add(labelKey, gbc);
        gbc.gridx = 1;
        gradientPanel.add(keyField, gbc);

        gbc.gridx = 0; gbc.gridy++;
        gradientPanel.add(labelDelay, gbc);
        gbc.gridx = 1;
        gradientPanel.add(delayField, gbc);

        gbc.gridx = 0; gbc.gridy++;
        gradientPanel.add(labelRepeat, gbc);
        gbc.gridx = 1;
        gradientPanel.add(repeatField, gbc);

        gbc.gridx = 0; gbc.gridy++; gbc.gridwidth = 2;
        gbc.anchor = GridBagConstraints.CENTER;
        gradientPanel.add(shiftBox, gbc);
        gbc.gridy++;
        gradientPanel.add(ctrlAltBox, gbc);
        gbc.gridy++;
        gradientPanel.add(alwaysOnTop, gbc);
        gbc.gridy++;
        gradientPanel.add(darkModeBox, gbc);
        gbc.gridy++;
        gradientPanel.add(startButton, gbc);

        // Always-on-Top-Funktion
        frame.setAlwaysOnTop(true);
        alwaysOnTop.addActionListener(e -> frame.setAlwaysOnTop(alwaysOnTop.isSelected()));

        // Dark Mode Umschaltung
        darkModeBox.addActionListener(e -> {
            boolean isDark = darkModeBox.isSelected();
            Color fg = isDark ? Color.WHITE : Color.BLACK;
            Color bg = isDark ? new Color(30, 30, 30) : Color.WHITE;

            for (Component comp : darkComponents) {
                comp.setForeground(fg);
                if (comp instanceof JTextField || comp instanceof JButton || comp instanceof JCheckBox) {
                    comp.setBackground(bg);
                }
            }

            gradientPanel.setForeground(fg);
            gradientPanel.setBackground(bg);
            gradientPanel.setDarkMode(isDark);
            gradientPanel.repaint();
            gradientPanel.revalidate();
        });

        // Start/Stop-Logik
        startButton.addActionListener(e -> {
            if (!running) {
                running = true;
                startButton.setText("Stop");
                int delay = Integer.parseInt(delayField.getText());
                int repeat = Integer.parseInt(repeatField.getText());
                String keyText = keyField.getText().toUpperCase();

                timer = new Timer();
                timer.scheduleAtFixedRate(new TimerTask() {
                    int count = 0;

                    public void run() {
                        if (!running || (repeat > 0 && count >= repeat)) {
                            timer.cancel();
                            startButton.setText("Start");
                            running = false;
                            return;
                        }

                        try {
                            Robot robot = new Robot();
                            if (ctrlAltBox.isSelected()) {
                                robot.keyPress(KeyEvent.VK_CONTROL);
                                robot.keyPress(KeyEvent.VK_ALT);
                            }
                            if (shiftBox.isSelected()) {
                                robot.keyPress(KeyEvent.VK_SHIFT);
                            }

                            int keyCode = KeyEvent.getExtendedKeyCodeForChar(keyText.charAt(0));
                            robot.keyPress(keyCode);
                            robot.keyRelease(keyCode);

                            if (shiftBox.isSelected()) robot.keyRelease(KeyEvent.VK_SHIFT);
                            if (ctrlAltBox.isSelected()) {
                                robot.keyRelease(KeyEvent.VK_ALT);
                                robot.keyRelease(KeyEvent.VK_CONTROL);
                            }
                        } catch (Exception ex) {
                            ex.printStackTrace();
                        }

                        count++;
                    }
                }, 0, delay);
            } else {
                running = false;
                if (timer != null) timer.cancel();
                startButton.setText("Start");
            }
        });

        frame.setContentPane(gradientPanel);
        frame.setVisible(true);
    }

    static class GradientRepaintablePanel extends JPanel {
        private boolean darkMode = false;

        public void setDarkMode(boolean darkMode) {
            this.darkMode = darkMode;
        }

        private Color toGray(Color color) {
            int gray = (int)(0.3 * color.getRed() + 0.59 * color.getGreen() + 0.11 * color.getBlue());
            return new Color(gray, gray, gray);
        }

        @Override
        protected void paintComponent(Graphics g) {
            super.paintComponent(g);
            Graphics2D g2d = (Graphics2D) g;
            int width = getWidth();
            int height = getHeight();

            Color[] colors;
            if (darkMode) {
                colors = new Color[] {
                    toGray(new Color(0x6a00fc)),
                    toGray(new Color(0xff0e93)),
                    toGray(new Color(0xffa10c)),
                    toGray(new Color(0xff4360))
                };
            } else {
                colors = new Color[] {
                    new Color(0x6a00fc),
                    new Color(0xff0e93),
                    new Color(0xffa10c),
                    new Color(0xff4360)
                };
            }

            float[] fractions = {0.0f, 0.4f, 0.8f, 1.0f};
            LinearGradientPaint paint = new LinearGradientPaint(0, 0, 0, height, fractions, colors);
            g2d.setPaint(paint);
            g2d.fillRect(0, 0, width, height);
        }
    }
}
